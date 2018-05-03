"""
This sample demonstrates an implementation of the Lex Code Hook Interface
in order to serve a sample bot which manages reservations for hotel rooms and car rentals.
Bot, Intent, and Slot models which are compatible with this sample can be found in the Lex Console
as part of the 'BookTrip' template.

For instructions on how to set up and test this bot, as well as additional samples,
visit the Lex Getting Started documentation http://docs.aws.amazon.com/lex/latest/dg/getting-started.html.
"""

import math
import dateutil.parser
import datetime
import time
import os
import logging
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

sqs = boto3.client('sqs')
sqsurl = 'https://sqs.us-east-1.amazonaws.com/188021121519/AI_SQS'
# --- Helpers that build all of the responses ---


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


# --- Helper Functions ---


def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None


# def isvalid_city(city):
#     valid_cities = ['new york', 'los angeles', 'chicago', 'houston', 'philadelphia', 'phoenix', 'san antonio',
#                     'san diego', 'dallas', 'san jose', 'austin', 'jacksonville', 'san francisco', 'indianapolis',
#                     'columbus', 'fort worth', 'charlotte', 'detroit', 'el paso', 'seattle', 'denver', 'washington dc',
#                     'memphis', 'boston', 'nashville', 'baltimore', 'portland']
#     return city.lower() in valid_cities
def sendSQS(message):
    MessageAttribute = {
        'Title': {
            'DataType': 'String',
            'StringValue': 'The Whistler'
        }
    }
    response = sqs.send_message(QueueUrl=sqsurl, MessageBody= message)
    print("This is response",response.get('MessageId'))
    #print(response.get('MD5OfMessageBody'))
    return response

def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }

def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def validate_order_dinner(cuisine_type, date, diningtime, number_of_people, location, phone_number):
    cuisine_types = ['french', 'italian', 'chinese', 'thailand', 'japanese']
    if cuisine_type is not None and cuisine_type.lower() not in cuisine_types:
        return build_validation_result(False,
                                       'Cuisine',
                                       'We do not have {}, would you like a different type of dinner?  '
                                       'Our most popular cuisine are Chinese'.format(cuisine_type))
    if date is not None:
        if not isvalid_date(date):
            return build_validation_result(False, 'DiningDate',
                                           'Sorry. We don\'t recognize the date you entered. Can you enter again?')
        elif datetime.datetime.strptime(date, '%Y-%m-%d').date() < datetime.date.today():
            return build_validation_result(False, 'DiningDate',
                                           'You can reserve a seat from tomorrow onwards.  What day would you like to choose?')


    if diningtime is not None:
        if len(diningtime) != 5:
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'DiningTime', None)

        hour, minute = diningtime.split(':')
        hour = parse_int(hour)
        minute = parse_int(minute)
        if math.isnan(hour) or math.isnan(minute):
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'DiningTime', None)

        if hour < 10 or hour > 17:
            # Outside of business hours
            return build_validation_result(False, 'DiningTime', 'Our business hours are from ten a m. to five pm. Can you specify a time during this range?')

    if phone_number is not None:
        if not phone_number.isdigit() or len(phone_number) != 10:
            return build_validation_result(False, 'PhoneNumber', 'Please input a valid phone number!')

    if number_of_people is not None:
        if int(number_of_people) > 50:
            return build_validation_result(False, 'NumberOfPeople',
                                           'Sorry we only provide restaurant recommendations less than 50 people.')
        if int(number_of_people) <= 0:
            return build_validation_result(False, 'NumberOfPeople',
                                           'Please input a valid integer number larger than zero!')

    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """


def order_dining(intent_request):
    """
    Performs dialog management and fulfillment for booking a car.

    Beyond fulfillment, the implementation for this intent demonstrates the following:
    1) Use of elicitSlot in slot validation and re-prompting
    2) Use of sessionAttributes to pass information that can be used to guide conversation
    """
    slots = intent_request['currentIntent']['slots']
    location = slots['Location']
    cuisine_type = slots['Cuisine']
    dtime = slots['DiningTime']
    ddate = slots['DiningDate']
    number_of_people = slots['NumberOfPeople']
    phone_number = slots['PhoneNumber']

    confirmation_status = intent_request['currentIntent']['confirmationStatus']
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    last_confirmed_reservation = try_ex(lambda: session_attributes['lastConfirmedReservation'])
    if last_confirmed_reservation:
        last_confirmed_reservation = json.loads(last_confirmed_reservation)
    confirmation_context = try_ex(lambda: session_attributes['confirmationContext'])

    # Load confirmation history and track the current reservation.
    reservation = json.dumps({
        "Location": location,
        "Cuisine": cuisine_type,
        "DiningTime": dtime,
        "DiningDate": ddate,
        "NumberOfPeople": number_of_people,
        "PhoneNumber": phone_number
    })
    # sendSQS(reservation)
    session_attributes['currentReservation'] = reservation

    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_order_dinner(cuisine_type, ddate, dtime, number_of_people, location, phone_number)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message']
            )

        # Determine if the intent (and current slot settings) has been denied.  The messaging will be different
        # if the user is denying a reservation he initiated or an auto-populated suggestion.
        if confirmation_status == 'Denied':
            # Clear out auto-population flag for subsequent turns.
            try_ex(lambda: session_attributes.pop('confirmationContext'))
            try_ex(lambda: session_attributes.pop('currentReservation'))
            if confirmation_context == 'AutoPopulate':
                return elicit_slot(
                    session_attributes,
                    intent_request['currentIntent']['name'],
                    {
                        'Location': None,
                        'Cuisine': None,
                        'DiningTime': None,
                        'DiningDate': None,
                        'NumberOfPeople': None,
                        'PhoneNumber': None
                    },
                    'Location',
                    {
                        'contentType': 'PlainText',
                        'content': 'Where would you like to make your dining reservation?'
                    }
                )

            return delegate(session_attributes, intent_request['currentIntent']['slots'])

        if confirmation_status == 'None':
            #sendSQS(reservation)
            # Otherwise, let native DM rules determine how to elicit for slots and/or drive confirmation.
            return delegate(session_attributes, intent_request['currentIntent']['slots'])

        # If confirmation has occurred, continue filling any unfilled slot values or pass to fulfillment.
        if confirmation_status == 'Confirmed':
            # Remove confirmationContext from sessionAttributes so it does not confuse future requests
            try_ex(lambda: session_attributes.pop('confirmationContext'))
            # if confirmation_context == 'AutoPopulate':
            #     if not driver_age:
            #         return elicit_slot(
            #             session_attributes,
            #             intent_request['currentIntent']['name'],
            #             intent_request['currentIntent']['slots'],
            #             'DriverAge',
            #             {
            #                 'contentType': 'PlainText',
            #                 'content': 'How old is the driver of this car rental?'
            #             }
            #         )
            #     elif not car_type:
            #         return elicit_slot(
            #             session_attributes,
            #             intent_request['currentIntent']['name'],
            #             intent_request['currentIntent']['slots'],
            #             'CarType',
            #             {
            #                 'contentType': 'PlainText',
            #                 'content': 'What type of car would you like? Popular models are '
            #                           'economy, midsize, and luxury.'
            #             }
            #         )
            sendSQS(reservation)
            return delegate(session_attributes, intent_request['currentIntent']['slots'])

    # Booking the car.  In a real application, this would likely involve a call to a backend service.
    logger.debug('bookDinner at={}'.format(reservation))
    del session_attributes['currentReservation']
    session_attributes['lastConfirmedReservation'] = reservation
    sendSQS(reservation)
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Thanks, I have placed your reservation.'
        }
    )


def Greeting(intent_request):
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Hi there. May I help you?'
        }
    )


def Thanks(intent_request):
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'You are welcome!'
        }
    )


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug(
        'dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'DiningSuggestions':
        return order_dining(intent_request)
    if intent_name == 'Greeting':
        return Greeting(intent_request)
    if intent_name == 'Thanks':
        return Thanks(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
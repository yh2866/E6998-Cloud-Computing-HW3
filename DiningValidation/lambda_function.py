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
import re
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


def isvalid_city(city):
    # valid_cities = ['new york', 'los angeles', 'chicago', 'houston', 'philadelphia', 'phoenix', 'san antonio',
    #                 'san diego', 'dallas', 'san jose', 'austin', 'jacksonville', 'san francisco', 'indianapolis',
    #                 'columbus', 'fort worth', 'charlotte', 'detroit', 'el paso', 'seattle', 'denver', 'washington dc',
    #                 'memphis', 'boston', 'nashville', 'baltimore', 'portland']
    valid_cities = ['new york']
    return city.lower() in valid_cities
    
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
    cuisine_types = ['french', 'american', 'chinese']
    if cuisine_type is not None and cuisine_type.lower() not in cuisine_types:
        return build_validation_result(False,
                                       'Cuisine',
                                       'We do not have {}, would you like a different type of dinner?  '
                                       'Our most popular cuisine are Chinese'.format(cuisine_type))
    if date is not None:
        if not re.match('([0-9]{3}[1-9]|[0-9]{2}[1-9][0-9]{1}|[0-9]{1}[1-9][0-9]{2}|[1-9][0-9]{3})-(((0[13578]|1[02])-(0[1-9]|[12][0-9]|3[01]))|((0[469]|11)-(0[1-9]|[12][0-9]|30))|(02-(0[1-9]|[1][0-9]|2[0-8])))',date):
            return build_validation_result(False, 'DiningDate',
                                           'Sorry. We don\'t recognize the date you entered, use a format 2018-04-01. Can you enter again?')
        elif datetime.datetime.strptime(date, '%Y-%m-%d').date() < datetime.date.today():
            return build_validation_result(False, 'DiningDate',
                                           'You can reserve a seat from tomorrow onwards.  What day would you like to choose?')


    if diningtime is not None:
        if not re.match('^[01]?[0-9]\:[0-5][0-9]',diningtime):
            return build_validation_result(False, 'DiningTime', 'Sorry. We don’t recognize the time you entered, use the format 18:00. Can you enter again?')
        diningtime = str(re.search('^[01]?[0-9]\:[0-5][0-9]',diningtime).group())
            # Not a valid time; use a prompt defined on the build-time model.
            
        
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
    
    if location is not None:
        if not isvalid_city(location):
            return build_validation_result(False, 'Location',
                                           'Please input a valid location in USA, for example new york')
    
    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """

def check_full_attr(cuisine_type, date, exact_time, number_of_people, location, phone_number):
    if cuisine_type is not None and date is not None and exact_time is not None and number_of_people is not None and location is not None and phone_number is not None:
        return True


def order_dining(intent_request):
    """
    Performs dialog management and fulfillment for booking a car.

    Beyond fulfillment, the implementation for this intent demonstrates the following:
    1) Use of elicitSlot in slot validation and re-prompting
    2) Use of sessionAttributes to pass information that can be used to guide conversation
    """
    slots =try_ex(lambda: intent_request['currentIntent']['slots'])
    location = try_ex(lambda: slots['Location'])
    cuisine_type = try_ex(lambda: slots['Cuisine'])
    dtime = try_ex(lambda: slots['DiningTime'])
    ddate = try_ex(lambda: slots['DiningDate'])
    if ddate != None:
        if ddate.lower() =="today":
            ddate = str(datetime.date.today())
            slots['DiningDate'] = ddate
        elif ddate.lower() == "tomorrow":
            ddate = str((datetime.date.today()+datetime.timedelta(days=1)))
            slots['DiningDate'] = ddate
        
    # print (ddate)
    number_of_people = try_ex(lambda: slots['NumberOfPeople'])
    phone_number =try_ex(lambda:  slots['PhoneNumber'])

    confirmation_status = try_ex(lambda: intent_request['currentIntent']['confirmationStatus'])
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


        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
    #if intent_request['invocationSource'] == 'DialogCodeHook':
    validation_result = validate_order_dinner(cuisine_type, ddate, dtime, number_of_people, location, phone_number)
    if not validation_result['isValid']:
        slots[validation_result['violatedSlot']] = None
        return elicit_slot(
            session_attributes,
            intent_request['currentIntent']['name'],
            slots,
            validation_result['violatedSlot'],
            validation_result['message'])
            
        # if validation_result['isValid'] and check_full_attr(cuisine_type, ddate, dtime, number_of_people, location, phone_number):
        #     session_attributes['confirmationContext']='Confirmed'
        #     intent_request['currentIntent']['confirmationStatus']='Confirmed'
        #     return confirm_intent(session_attributes, 
        #         intent_request['currentIntent']['name'],
        #         slots,
        #         'We are processing your information')
        
    return delegate(session_attributes,slots)




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

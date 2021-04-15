import logging
import re
import datetime
import isv
import configstore

from html import escape
from time import sleep
from strings import lang as _
from telegram import (
    Update,
    ParseMode,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Updater,
    Filters,
    CommandHandler,
    MessageHandler,
    CallbackContext
)


#
# helpers
#

def get_markup() -> ReplyKeyboardMarkup:
    button = [
        [
            _('status'),
            _('generation')
        ],
        [
            _('gs'),
            _('ri'),
            _('errors')
        ]
    ]
    return ReplyKeyboardMarkup(button, one_time_keyboard=False)


def reply(update: Update, text: str) -> None:
    update.message.reply_text(text,
                              reply_markup=get_markup(),
                              parse_mode=ParseMode.HTML)


#
# command/message handlers
#

def start(update: Update, context: CallbackContext) -> None:
    reply(update, 'Select a command on the keyboard.')


def msg_status(update: Update, context: CallbackContext) -> None:
    try:
        gs = isv.general_status()

        # render response
        power_direction = gs['battery_power_direction'].lower()
        power_direction = re.sub(r'ge$', 'ging', power_direction)

        charging_rate = ''
        if power_direction == 'charging':
            charging_rate = ' @ %s %s' % tuple(gs['battery_charging_current'])
        elif power_direction == 'discharging':
            charging_rate = ' @ %s %s' % tuple(gs['battery_discharge_current'])

        html = '<b>Battery:</b> %s %s' % tuple(gs['battery_voltage'])
        html += ' (%s%s, ' % tuple(gs['battery_capacity'])
        html += '%s%s)' % (power_direction, charging_rate)

        html += '\n<b>Load:</b> %s %s' % tuple(gs['ac_output_active_power'])
        html += ' (%s%%)' % (gs['output_load_percent'][0])

        if gs['pv1_input_power'][0] > 0:
            html += '\n<b>Input power:</b> %s%s' % tuple(gs['pv1_input_power'])

        if gs['grid_voltage'][0] > 0 or gs['grid_freq'][0] > 0:
            html += '\n<b>Generator:</b> %s %s' % tuple(gs['grid_voltage'])
            html += ', %s %s' % tuple(gs['grid_freq'])

        # send response
        reply(update, html)
    except Exception as e:
        logging.exception(str(e))
        reply(update, 'exception: ' + str(e))


def msg_generation(update: Update, context: CallbackContext) -> None:
    try:
        today = datetime.date.today()
        yday = today - datetime.timedelta(days=1)
        yday2 = today - datetime.timedelta(days=2)

        gs = isv.general_status()
        sleep(0.1)

        gen_today = isv.day_generated(today.year, today.month, today.day)
        gen_yday = None
        gen_yday2 = None

        if yday.month == today.month:
            sleep(0.1)
            gen_yday = isv.day_generated(yday.year, yday.month, yday.day)

        if yday2.month == today.month:
            sleep(0.1)
            gen_yday2 = isv.day_generated(yday2.year, yday2.month, yday2.day)

        # render response
        html = '<b>Input power:</b> %s %s' % tuple(gs['pv1_input_power'])
        html += ' (%s %s)' % tuple(gs['pv1_input_voltage'])

        html += '\n<b>Today:</b> %s Wh' % (gen_today['wh'])

        if gen_yday is not None:
            html += '\n<b>Yesterday:</b> %s Wh' % (gen_yday['wh'])

        if gen_yday2 is not None:
            html += '\n<b>The day before yesterday:</b> %s Wh' % (gen_yday2['wh'])

        # send response
        reply(update, html)
    except Exception as e:
        logging.exception(str(e))
        reply(update, 'exception: ' + str(e))


def msg_gs(update: Update, context: CallbackContext) -> None:
    try:
        status = isv.general_status(as_table=True)
        reply(update, status)
    except Exception as e:
        logging.exception(str(e))
        reply(update, 'exception: ' + str(e))


def msg_ri(update: Update, context: CallbackContext) -> None:
    try:
        rated = isv.rated_information(as_table=True)
        reply(update, rated)
    except Exception as e:
        logging.exception(str(e))
        reply(update, 'exception: ' + str(e))


def msg_errors(update: Update, context: CallbackContext) -> None:
    try:
        faults = isv.faults(as_table=True)
        reply(update, faults)
    except Exception as e:
        logging.exception(str(e))
        reply(update, 'exception: ' + str(e))


def msg_all(update: Update, context: CallbackContext) -> None:
    reply(update, "Command not recognized. Please try again.")


if __name__ == '__main__':
    config = configstore.get_config()

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    updater = Updater(configstore.get_token(), request_kwargs={'read_timeout': 6, 'connect_timeout': 7})
    dispatcher = updater.dispatcher

    user_filter = Filters.user(configstore.get_admins())

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.text(_('status')) & user_filter, msg_status))
    dispatcher.add_handler(MessageHandler(Filters.text(_('generation')) & user_filter, msg_generation))
    dispatcher.add_handler(MessageHandler(Filters.text(_('gs')) & user_filter, msg_gs))
    dispatcher.add_handler(MessageHandler(Filters.text(_('ri')) & user_filter, msg_ri))
    dispatcher.add_handler(MessageHandler(Filters.text(_('errors')) & user_filter, msg_errors))
    dispatcher.add_handler(MessageHandler(Filters.all & user_filter, msg_all))

    # start the bot
    updater.start_polling()

    # run the bot until the user presses Ctrl-C or the process receives SIGINT, SIGTERM or SIGABRT
    updater.idle()

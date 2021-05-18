'''
Tests for aiocasambi
'''
import argparse
import asyncio
import logging
import logging.handlers
import sys
import random
import os
import yaml
import aiohttp
import async_timeout

from pprint import pprint, pformat

sys.path.append(os.path.split(os.path.dirname(sys.argv[0]))[0])

try:
    import aiocasambi
except ModuleNotFoundError as err:
    pprint(sys.path)
    raise err

LOGGER = logging.getLogger(__name__)


def signalling_callback(signal, data):
    LOGGER.info(f"signalling_callback {signal}, {data}")


async def get_casambi_controller(
    *,
    email,
    user_password,
    network_password,
    api_key,
    session,
    sslcontext,
    callback,
    wire_id
):
    """Setup Casambi controller and verify credentials."""
    controller = aiocasambi.Controller(
        email=email,
        user_password=user_password,
        network_password=network_password,
        api_key=api_key,
        websession=session,
        sslcontext=sslcontext,
        wire_id=wire_id,
        callback=callback,
    )

    try:
        with async_timeout.timeout(10):
            await controller.create_user_session()
            await controller.create_network_session()
        return controller

    except aiocasambi.LoginRequired:
        LOGGER.warning("Connected to casambi but couldn't log in")

    except aiocasambi.Unauthorized:
        LOGGER.warning("Connected to casambi but not registered")

    except (asyncio.TimeoutError, aiocasambi.RequestError):
        LOGGER.exception('Error connecting to the Casambi')

    except aiocasambi.AiocasambiException:
        LOGGER.exception('Unknown Casambi communication error occurred')


def parse_config(config_file='casambi.yaml'):
    config = {}

    if not os.path.isfile(config_file):
        return config   # empty dict

    with open(config_file, 'r') as stream:
        config = yaml.safe_load(stream)

    return config


def setup_logger(*, debug=False):
    root = logging.getLogger()
    formatter = logging.Formatter(
        '%(asctime)s %(process)d %(processName)-10s %(name)-8s %(funcName)-8s %(levelname)-8s %(message)s')

    if debug:
        max_bytes = 3 * 10**7
        backup_count = 10
        file_handler = logging.handlers.RotatingFileHandler(
            'casambi.log',
            'a',
            max_bytes,
            backup_count
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    if debug:
        root.setLevel(logging.DEBUG)


def print_unit_information(*, controller, unit_id):
    unit = controller.get_unit(unit_id=unit_id)
    LOGGER.info(f"unit: {unit}")

    return


async def main(
    *,
    email,
    user_password,
    network_password,
    units,
    api_key,
    wire_id=1,
    sslcontext=False
):
    """Main function."""
    LOGGER.info("Starting aioCasambi")

    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    websession = aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=False),
        timeout=timeout
    )

    controller = await get_casambi_controller(
        email=email,
        user_password=user_password,
        network_password=network_password,
        api_key=api_key,
        wire_id=wire_id,
        sslcontext=sslcontext,
        session=websession,
        callback=signalling_callback,
    )

    if not controller:
        LOGGER.error("Couldn't connect to Casambi controller")
        await websession.close()
        return

    await controller.initialize()

    await controller.start_websocket()

    try:
        while True:
            await asyncio.sleep(60)
            network_state_data = None

            try:
                network_state_data = await controller.get_network_state()
            except AttributeError as err:
                error_msg = f"Caught AttributeError: {err} "
                error_msg += f"dir(controller): {dir(controller)}"
                LOGGER.error(error_msg)
                raise err

            msg = f"Current Units state: {controller.get_units()}"
            msg += f"websocket: {controller.get_websocket_state()} "
            msg += f"network_state: {pformat(network_state_data)}"

            LOGGER.info(msg)

            if controller.get_websocket_state() == 'disconnected':
                await controller.reconnect()

            for unit_id in units:
                print_unit_information(controller=controller, unit_id=unit_id)

                LOGGER.info(f"Turn unit: {unit_id} on!")
                await controller.turn_unit_on(unit_id=unit_id)
                await asyncio.sleep(60)

                print_unit_information(controller=controller, unit_id=unit_id)

                LOGGER.info(f"Turn unit: {unit_id} off!")
                await controller.turn_unit_off(unit_id=unit_id)
                await asyncio.sleep(60)

                if controller.unit_supports_color_temperature(unit_id=unit_id):
                    (min_color_temp, max_color_temp, _) = \
                        controller.get_supported_color_temperature(
                            unit_id=unit_id)

                    color_temp = random.randint(min_color_temp, max_color_temp)

                    info_msg = f"Setting unit: {unit_id} "
                    info_msg += f"to Color temperature: {color_temp}"
                    LOGGER.info(info_msg)

                    await controller.set_unit_color_temperature(
                        unit_id=unit_id,
                        value=color_temp
                        )
                    await asyncio.sleep(60)

                    print_unit_information(
                        controller=controller, unit_id=unit_id)

                    LOGGER.info(f"Turn unit: {unit_id} off!")
                    await controller.turn_unit_off(unit_id=unit_id)
                    await asyncio.sleep(60)

    except asyncio.CancelledError as err:
        LOGGER.debug(f"Caught asyncio.CancelledError in main loop: {err}")
        pass
    except Exception as err:
        LOGGER.debug(f"Caught Exception in main loop: {err}")
        raise err
    finally:
        controller.stop_websocket()
        await websession.close()


if __name__ == "__main__":
    units = set()
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", type=str, required=False)
    parser.add_argument("--api_key", type=str, required=False)
    parser.add_argument("--user_password", type=str, required=False)
    parser.add_argument("--network_password", type=str, required=False)
    parser.add_argument("-D", "--debug", action="store_true")
    args = parser.parse_args()

    config = parse_config()

    if args.email:
        config['email'] = args.email

    if args.user_password:
        config['user_password'] = args.user_password

    if args.network_password:
        config['network_password'] = args.network_password

    if args.api_key:
        config['api_key'] = args.api_key

    if args.debug:
        config['debug'] = True

    if 'debug' not in config:
        config['debug'] = False

    if 'wire_id' not in config:
        config['wire_id'] = random.randint(10, 60)

    if 'unit' in config:
        units.add(config['unit'])

    if 'units' in config:
        for elem in config['units']:
            units.add(elem)

    units = sorted(units)

    if len(units) == 0:
        # Add unit_id 1 to the empty set
        units.add(1)

    setup_logger(debug=config['debug'])

    LOGGER.debug(f"Configuration: {pformat(config)}")

    try:
        asyncio.run(
            main(
                email=config['email'],
                user_password=config['user_password'],
                network_password=config['network_password'],
                api_key=config['api_key'],
                wire_id=config['wire_id'],
                units=units
            )
        )
    except KeyboardInterrupt:
        pass

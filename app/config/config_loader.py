import argparse
import json
import logging
import os
import re
import ipaddress
import sys
import threading
import dns.rdatatype
import dns.resolver
import dns.exception

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from typing import List

from app.assets.subdomains import THE_MOST_USED_DOMAINS

logger = logging.getLogger(__name__)

class DNSConfig:
    def __init__(self, servers: List[str], health_check_domain: str):
        self.servers = servers
        self.health_check_domain = health_check_domain
    
    def __repr__(self):
        return f"DNSConfig(resolution_timeout_milliseconds={self.resolution_timeout_milliseconds}, retries={self.retries}, servers={self.servers}, health_check_domain={self.health_check_domain})"

class AppConfig:
    def __init__(self, subdomain_word_list_file_path: str, domains_to_resolve: set[str], max_thread_count: int, dns: DNSConfig, output_file_path: str = "./result.txt", flat_result: bool = False, debug: bool = False, subdomain_word_list: set[str] = None):
        self.subdomain_word_list_file_path = subdomain_word_list_file_path
        self.domains_to_resolve = set(domains_to_resolve)
        self.subdomain_word_list = None if subdomain_word_list is None else set(subdomain_word_list)
        self.max_thread_count = max_thread_count
        self.output_file_path = output_file_path
        self.flat_result = flat_result
        self.debug = debug
        self.dns = DNSConfig(**dns)

    def __repr__(self):
        return f"AppConfig(subdomain_word_list_file_path={self.subdomain_word_list_file_path}, subdomain_word_list={self.subdomain_word_list} max_thread_count={self.max_thread_count}, dns={self.dns})"

def load_config(cancellation_event: threading.Event, parsed_args: argparse.Namespace | None = None, config_filename: str='config.json') -> AppConfig:
    """Loads the configuration from the specified JSON file or passed arguments."""
    
    if parsed_args is not None:
        config = AppConfig(
            subdomain_word_list_file_path=parsed_args.subdomain_word_list_file_path,
            domains_to_resolve=[domain.strip() for domain in parsed_args.domains_to_resolve.split(",")],
            dns={'servers': [server.strip() for server in parsed_args.dns_servers.split(",")], 'health_check_domain': parsed_args.health_check_domain},
            max_thread_count=parsed_args.max_thread_count,
            output_file_path=parsed_args.output_file_path,
            flat_result=parsed_args.flat_result
        )        
    else:
        config_path = os.path.join(os.path.dirname(__file__), config_filename)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file '{config_filename}' not found.")
        try:
            with open(config_path, 'r') as f:
                config_json = json.load(f)
                config = AppConfig(**config_json)
        except FileNotFoundError: 
            raise FileNotFoundError(f"Configuration file '{config_filename}' not found.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON configuration from {config_filename}: {e}")

    if config.debug:
        logger.setLevel(logging.DEBUG)
        logging.debug(f"Debug mode is enabled. Configuration: {config}")

    if config.subdomain_word_list_file_path is None or config.subdomain_word_list_file_path == "":
        logger.info(f"'subdomain_word_list_file_path' is not set in the configuration '{config_filename}' or provided via argument. Using default list with the most 5000 used domains.")
        subdomains: set[str] = THE_MOST_USED_DOMAINS
    else:
        try:
            with open(config.subdomain_word_list_file_path, 'r') as f:
                subdomains: set[str] = f.readlines()
        except IOError as e:
            raise ValueError(f"Error reading subdomain word list file: {e}")

    config.subdomain_word_list = get_valid_subdomains(subdomains);
    config.dns.servers = get_validated_dns_servers(config.dns.health_check_domain, config.dns.servers, cancellation_event)

    return config

def get_valid_subdomains(subdomains: set[str]) -> set[str]:
    """Validates the subdomains and returns a list of valid ones."""
    valid_subdomains: set[str] = set()
    HOSTNAME_REGEX = re.compile(r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)(\.[A-Za-z0-9_-]{1,63})*$")

    for subdomain in subdomains:
        subdomain = subdomain.strip()
        response = HOSTNAME_REGEX.fullmatch(subdomain)
        if response:
            valid_subdomains.add(subdomain)
        else:
            logging.warning(f"Invalid subdomain: {subdomain}")
          
    number_of_subdomains = len(valid_subdomains) + 1
    logger.info(f"Read '{number_of_subdomains}' valid subdomain{'s' if number_of_subdomains > 1 else ''}.")
    return valid_subdomains

def get_validated_dns_servers(health_check_domain: str, dns_servers: List[str], cancellation_event: threading.Event) -> List[str]:
    for server in dns_servers:
        try:
            ipaddress.ip_address(server)
        except ValueError:
            logger.warning(f"Invalid IP address for DNS server: {server}")
            dns_servers.remove(server)
            continue
    
    if len(dns_servers) == 0:
        logger.error("No valid DNS servers found.")
        raise ValueError("No valid DNS servers found.")
    
    for server in dns_servers:
        try:
            # Check if the DNS server is reachable
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [server]
            
            if cancellation_event.is_set():
                logger.debug("Cancellation event set. Exiting...")
                sys.exit(0)
            resolver.resolve(health_check_domain, dns.rdatatype.A);

            logger.debug(f"DNS server '{server}' was able to resolve health check domain '{health_check_domain}'.")
        except dns.exception.DNSException as e:
            logger.warning(f"DNS server {server} is not reachable. Error: '{e}'")
            dns_servers.remove(server)
            continue
        
    if len(dns_servers) == 0:
        raise ValueError("No reachable DNS servers found.")
    
    return dns_servers
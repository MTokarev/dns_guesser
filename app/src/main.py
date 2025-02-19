import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
from itertools import cycle
import logging
import signal
import sys
import os
import threading
import time
import dns.rdatatype
import dns.resolver
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from collections import defaultdict
from typing import DefaultDict, List, Optional
from app.config.config_loader import load_config, AppConfig

# Cancellation event
cancellation_event = threading.Event()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    start_time = time.perf_counter()

    logger.info("Press Ctrl+C 💥 to cancel the execution .")
    
    # Register signal handlers for graceful shutdown (Ctrl+C or termination)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    parsed_args = parse_args()
    if parsed_args.config_file:
        config = load_config(cancellation_event, config_filename=parsed_args.config_file)
    else:
        config = load_config(cancellation_event, parsed_args=parsed_args)

    result = resolve_in_parallel(config)

    if config.compact_networks:
        logger.info("Converting IPs to CIDR notation.")
        # Flatten the result to a single list of IPs
        ip_addresses = set([ip for ips in result.values() for ip in ips])
        result = {"compacted_networks": compact_ips(ip_addresses)}

    write_results_to_file(result, config.output_file_path, config.flat_result | config.compact_networks)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    logger.info(f"Elapsed time: {elapsed_time:.2f} seconds ⏱️.")


def resolve_domain(server: str, domain: str, record_type: dns.rdatatype = dns.rdatatype.A, nested_calls: int = 3, current_call: int = 1) -> tuple[str, str, Optional[List[str]]]:
    """
    Resolves a domain using the specified DNS server and record type.

    Returns:
        A tuple containing the domain, server, and a list of resolved IP addresses or None if not resolved.
    """
    if cancellation_event.is_set():
        return domain, server, None

    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [server]
        result = resolver.resolve(domain)
        addresses = [rdata.address for rdata in result]
        
        return domain, server, addresses
    except dns.resolver.NoAnswer:
        if record_type != dns.rdatatype.CNAME and current_call <= nested_calls:
            return resolve_domain(server, domain, dns.rdatatype.CNAME, current_call=current_call + 1)
        else:
            return domain, server,  None
    except Exception:
        return domain, server, None  # Return None for unresolved subdomains

def resolve_in_parallel(config: AppConfig) -> DefaultDict[str, set[str]]:
    """
    Resolves subdomains in parallel using multiple DNS servers.

    Returns:
        A dictionary mapping each domain to a set of resolved IP addresses.
    """
    
    resolved: DefaultDict[str, set[str]] = defaultdict(set)
    # Create a thread pool
    with ThreadPoolExecutor(max_workers=config.max_thread_count) as executor:  # Adjust worker count as needed
        future_to_subdomain = {}

        dns_servers = cycle(config.dns.servers)

        # Submit tasks
        for domain in config.domains_to_resolve:
            
            # Add domain itself
            server = next(dns_servers)
            future = executor.submit(resolve_domain, server, domain)
            future_to_subdomain[future] = domain

            for subdomain in config.subdomain_word_list:
                if cancellation_event.is_set():
                    logger.debug("Cancellation requested. Exiting...")
                    return resolved
                server = next(dns_servers)
                future = executor.submit(resolve_domain, server, f"{subdomain}.{domain}")
                future_to_subdomain[future] = subdomain  

        # Collect results
        for future in as_completed(future_to_subdomain):
            if cancellation_event.is_set():
                logger.debug("Cancellation requested. Exiting...")
                return resolved
            domain, server, ip_addresses = future.result()
            if ip_addresses is not None and len(ip_addresses) > 0:
                resolved[domain].update(ip_addresses)
                logger.info(f"DNS server '{server}' resolved '{domain}' to '{', '.join(ip_addresses)}'.")

    logger.info("All records have been resolved ✅.")

    return resolved  

def write_results_to_file(resolved: DefaultDict[str, set[str]], file_path: str, file_flat_or_compressed: bool = False):
    """Writes the resolved subdomains to a file."""
    try:
        if cancellation_event.is_set():
            logger.debug("Cancellation requested. Exiting...")
            return
        with open(file_path, 'w') as f:

            if file_flat_or_compressed:
                logger.info("Writing results in flat format. To have the domain name in the line as a comment please remove the '-fr' or/and '-ct' flag.")
                distinct_ips = set()
                for domain in resolved.keys():
                    distinct_ips.update(resolved[domain])
                
                for ip in distinct_ips:
                    if cancellation_event.is_set():
                        logger.debug("Cancellation requested. Exiting...")
                        return
                    
                    f.write(f"{ip}\n")
            else:
                # If we made to this point, it means that the user wants the domain format
                logger.info("Writing results by adding domain for the each IP as a comment. To have flat format with one IP per line set the '-fr' flag.")
                
                sorted_by_duplicates: DefaultDict[str, set[str]] = defaultdict(set)
                
                for domain in resolved.keys():
                    for ip in resolved[domain]:
                        if ip in sorted_by_duplicates:
                            sorted_by_duplicates[ip].add(domain)
                        else:
                            sorted_by_duplicates[ip] = {domain}
                
                for ip in sorted_by_duplicates.keys():
                    if cancellation_event.is_set():
                            logger.debug("Cancellation requested. Exiting...")
                            return
                    f.write(f"{ip} # {', '.join(sorted_by_duplicates[ip])}\n")

    except IOError as e:
        logger.error(f"Error writing to file '{file_path}': {e}")
        return
    logger.info(f"Results written to '{file_path}' 📝.")

def parse_args() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Subdomain Resolver 🔎")

    # Adding required command-line arguments
    # Adding mutually exclusive group
    group = parser.add_mutually_exclusive_group(required=True)  # One argument in the group must be provided
    group.add_argument("-c", "--config-file", metavar="config.json", type=str, help="Path to the configuration file.")
    group.add_argument("-d", "--domains-to-resolve", metavar="'google.com,linkedin.com'", type=str, help="Comma-separated domains to resolve.")    

    # Optional arguments
    optional_group = parser.add_mutually_exclusive_group(required=False)  # One argument in the group must be provided
    optional_group.add_argument("-fr", "--flat-result", action="store_true", help="Writes results in flat format. Every line contains only an IP address. If not set, each domain will have its own section.")
    optional_group.add_argument("-ct", "--compact-networks", action="store_true", help="The result will be printed in CIDR notation flat format, but with this flag, IP addresses will be grouped by network if possible.")    
    
    parser.add_argument("-s", "--dns-servers", metavar="'8.8.8.8,8.8.4.4'", default="8.8.8.8,8.8.4.4", type=str, help="Comma-separated list of DNS servers to use. Default is '8.8.8.8,8.8.4.4'.")
    parser.add_argument("-sw", "--subdomain-word-list-file-path", metavar="subdomain_list.txt", default=None, type=str, help="Path to the subdomain word list file. If not provided, a default list with 5000 of the most used subdomains will be used.")
    parser.add_argument("-hc", "--health-check-domain", metavar="github.com", default="github.com", type=str, help="Domain for the DNS servers health check. The DNS server is considered valid if it can resolve the domain. Default is 'github.com'.")
    parser.add_argument("-o", "--output-file-path", metavar="dns_resolution_result.txt", default="dns_resolution_result.txt", type=str, help="Path to the result file. Default is './dns_resolution_result.txt'.")
    parser.add_argument("-t", "--max-thread-count", metavar=64, default=64, type=int, help="Maximum number of threads to use. Default is 64.")
    parser.add_argument("-db", "--debug", action="store_true", help="Outputs debug information.")
    return parser.parse_args()

def compact_ips(resolved: set[str]) -> set[str]:
    ip_networks = [ipaddress.IPv4Network(ip + "/32") for ip in sorted(resolved, key=lambda ip: int(ipaddress.IPv4Address(ip)))]
        
    # Collapse contiguous IPs into the smallest CIDRs
    merged_cidrs = list(ipaddress.collapse_addresses(ip_networks))
    
    return [str(cidr) for cidr in merged_cidrs]

# Signal handler to set the cancellation event
def signal_handler(sig, frame):
    logger.info("Cancellation requested. Cleaning up and exiting...")
    cancellation_event.set()

if __name__ == "__main__":
    main()
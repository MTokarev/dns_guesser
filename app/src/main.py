import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from typing import DefaultDict, List
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

    # Register signal handlers for graceful shutdown (Ctrl+C or termination)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if len(sys.argv) == 1:
        config = load_config(cancellation_event, config_filename="./config.json")
    else:
        parsed_args = parse_args()
        config = load_config(cancellation_event, parsed_args=parsed_args)

    result = resolve_in_parallel(config)
    write_results_to_file(result, config.output_file_path, config.flat_result)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")


def resolve_subdomain(server: str, domain: str, subdomain: str, record_type: dns.rdatatype = dns.rdatatype.A) -> tuple[str, str, List[str] | None]:
    """
    Tries to resolve a subdomain using the specified DNS server.
    
    Returns:
        (subdomain, resolved IP) if successful, otherwise (subdomain, None).
    """

    # Short circuit if cancellation is requested
    domain_to_resolve = f"{subdomain}.{domain}"
    if cancellation_event.is_set():
        return domain, server, domain_to_resolve, None
    
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [server]
        result = resolver.resolve(domain_to_resolve)
        addresses = [rdata.address for rdata in result]
        
        return domain, server, domain_to_resolve, addresses
    except dns.resolver.NoAnswer:
        if record_type != dns.rdatatype.CNAME:
            return resolve_subdomain(server, domain, subdomain, dns.rdatatype.CNAME)
        else:
            return domain, server, domain_to_resolve, None
    except Exception:
        return domain, server, domain_to_resolve, None  # Return None for unresolved subdomains

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

        dns_load_balancing_index = 0;

        # Submit tasks
        for domain in config.domains_to_resolve:
            for subdomain in config.subdomain_word_list:
                if cancellation_event.is_set():
                    logger.debug("Cancellation requested. Exiting...")
                    sys.exit(0)
                server = config.dns.servers[dns_load_balancing_index] 
                future = executor.submit(resolve_subdomain, server, domain, subdomain)
                future_to_subdomain[future] = subdomain

                # Load balancing across DNS servers
                dns_load_balancing_index = (dns_load_balancing_index + 1) % len(config.dns.servers)    

        # Collect results
        for future in as_completed(future_to_subdomain):
            if cancellation_event.is_set():
                logger.debug("Cancellation requested. Exiting...")
                sys.exit(0)
            domain, server, domain_to_resolve, ip_addresses = future.result()
            if ip_addresses is not None and len(ip_addresses) > 0:
                resolved[domain].update(ip_addresses)
                logger.info(f"DNS server '{server}' resolved '{domain_to_resolve}' to '{ip_addresses}'.")

    logger.info(f"Resolved {len(resolved)} subdomain{'s' if len(resolved) > 1 else ''}.")

    return resolved  

def write_results_to_file(resolved: DefaultDict[str, set[str]], file_path: str, file_flat: bool = False):
    """Writes the resolved subdomains to a file."""
    try:
        with open(file_path, 'w') as f:

            if file_flat:
                logger.info("Writing results in flat format. Each line is a resolved IP. To have the domain name, set the 'flat' option to 'true'.")
            else:
                logger.info("Writing results in domain format. Each domain has its own section. To have flat format with one IP per line only, set the 'flat' option to 'false'.")

            splitter = f"# {'-' * 30}\n"
            for domain in resolved.keys():
                if not file_flat:
                    f.write(splitter)
                    f.write(f"# Beginning of {domain}:\n")
                    f.write(splitter)
                for ip in resolved[domain]:
                    f.write(f"{ip}\n")
                
                if not file_flat:
                    f.write(splitter)
                    f.write(f"# End Of {domain}\n")
                    f.write(splitter)
    except IOError as e:
        logger.error(f"Error writing to file {file_path}: {e}")
        return
    logger.info(f"Results written to {file_path}")

def parse_args() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Subdomain Resolver")

    # Adding required command-line arguments
    parser.add_argument("-d", "--domains-to-resolve", metavar="'google.com,linkedin.com'", required=True, type=str, help="Comma-separated domains to resolve.")
    
    # Optional arguments
    parser.add_argument("-s", "--dns-servers", metavar="'8.8.8.8,8.8.4.4'", default="8.8.8.8,8.8.4.4", type=str, help="Comma-separated list of DNS servers to use. Default is '8.8.8.8,8.8.4.4'.")
    parser.add_argument("-sw", "--subdomain-word-list-file-path", metavar="subdomain_list.txt", default=None, type=str, help="Path to the subdomain word list file. If not provided, a default list with 5000 of the most used subdomains will be used.")
    parser.add_argument("-hc", "--health-check-domain", metavar="github.com", default="github.com", type=str, help="Domain for the DNS servers health check. The DNS server is considered valid if it can resolve the domain. Default is 'github.com'.")
    parser.add_argument("-o", "--output-file-path", metavar="dns_resolution_result.txt", default="dns_resolution_result.txt", type=str, help="Path to the result file. Default is './dns_resolution_result.txt'.")
    parser.add_argument("-fr", "--flat-result", action="store_true", help="Writes results in flat format. Every line contains only an IP address. If not set, each domain will have its own section.")
    parser.add_argument("-t", "--max-thread-count", metavar=64, default=64, type=int, help="Maximum number of threads to use. Default is 64.")
    parser.add_argument("-db", "--debug", action="store_true", help="Outputs debug information.")
    return parser.parse_args()

# Signal handler to set the cancellation event
def signal_handler(sig, frame):
    logger.info("Cancellation requested. Cleaning up and exiting...")
    cancellation_event.set()

if __name__ == "__main__":
    main()
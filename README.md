# DNS Guesser 🧐

A simple tool that allows you to resolve subdomains for the given domain list.

## Why ❓

This tool is designed for penetration testers (pentesters) and network administrators who need to resolve IP addresses for given domains and attempt to enumerate subdomains. It helps in identifying the IPs associated with domains and their subdomains, making it a valuable asset for tasks like firewall configuration and network mapping.

### Key Features:
- **Domain and Subdomain Resolution**: Resolves domain names and attempts to guess subdomains automatically.
- **IP Address Retrieval**: Retrieves the IP addresses associated with domains and subdomains.
- **Firewall Application**: Can be used for configuring firewalls like Linux IpTables and Windows Firewall, especially for blocking or filtering sites based on IP addresses instead of domain names.  
- **Automation-Friendly**: Can be put behind a cron job to regenerate a list of IP addresses and push it to firewalls, ensuring the firewall rules stay updated.


## How 🤔

By default, this CLI maintains the 5000 most used subdomains. You can override this list by providing a path to a file with custom subdomains (one domain per line, no regex support).

Example:
```txt
www
api
mail
www2.dev
```

It takes the domain you want to resolve, combines it with the subdomain, and sends the request to the DNS server. It tries to resolve the DNS ‘A’ record first, and if there is no answer, it falls back to ‘CNAME’.

## Is it slow? 🐌

It depends on the list of domains you want to resolve multiplied by the list of subdomains.
This CLI runs across multiple threads to speed up the process. The more threads, the faster it runs.

Example:
For two domains and 5000 subdomains, it usually takes 30-40 seconds to complete the task (64 threads are used).

## Help 🧑🏼‍💻

Here is the app help:
### Command-Line Arguments

| Short | Long                      | Type      | Default                          | Description |
|-------|---------------------------|----------|----------------------------------|-------------|
| `-c`  | `--config-file`           | `str`    | None                             | Path to the configuration file. |
| `-d`  | `--domains-to-resolve`    | `str`    | None                             | Comma-separated domains to resolve. |
| `-fr` | `--flat-result`           | `bool`   | `False`                          | Writes results in flat format (one IP per line). |
| `-ct` | `--compact-networks`      | `bool`   | `False`                          | Prints results in CIDR notation (grouping networks if possible). |
| `-s`  | `--dns-servers`           | `str`    | `"8.8.8.8,8.8.4.4"`              | Comma-separated list of DNS servers to use. |
| `-sw` | `--subdomain-word-list-file-path` | `str` | `None`                 | Path to the subdomain word list file. Uses a default list if not provided. |
| `-hc` | `--health-check-domain`   | `str`    | `"github.com"`                   | Domain used for DNS server health check. |
| `-o`  | `--output-file-path`      | `str`    | `"dns_resolution_result.txt"`    | Path to the result file. |
| `-t`  | `--max-thread-count`      | `int`    | `64`                             | Maximum number of threads to use. |
| `-db` | `--debug`                 | `bool`   | `False`                          | Enables debug output. |

### Usage Examples
- **Using a config file**:  
  ```sh
  python subdomain_resolver.py -c config.json
  ```
  **config.json**
  ```json
  {
    "subdomain_word_list_file_path": "/path/to/the/subdomain_word_list.txt",
    "flat_result": true,
    "debug": false,
    "output_file_path": "./result.txt",
    "max_thread_count": 100,
    "domains_to_resolve": [
      "github.com",
      "linkedin.com"
    ],
    "dns": {
      "servers": [
        "8.8.8.8",
        "8.8.4.4"
      ],
      "health_check_domain": "github.com"
    }
  }
  ```

- **CLI**:
```dns-guesser --domains-to-resolve "google.com, linkedin.com"
dns-guesser --domains-to-resolve "linkedin.com" --dns-servers "1.1.1.1" --subdomain-word-list-file-path ./subdomains.txt --health-check-domain github.com --output-file-path ./result.txt --flat-result -t 100 --debug
```

## How to get it 🚀

Make sure that you have at least Python `3.10` version installed.

The easiest way is to install it via `pip`:

`pip install dns-guesser`

## What is the source for 5000 subdomains

Special thanks 🎸 goes to the https://github.com/danielmiessler/SecLists repo.

## Output file

### Flat
```txt
1.1.1.1
1.1.1.2
8.8.1.1
```

### Not flat
```txt
8.8.8.8 # ns1.google.com, ns2.google.com
1.1.1.1 # domain.com, www.example.com
1.2.1.2 # something.example.com
```

### Compacted
```txt
192.168.1.0/23
192.168.2.1/32
175.20.11.0/28
```
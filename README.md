# DNS Guesser 🧐

A simple tool that allows you to resolve subdomains for the given domain list.

## Why ❓

Firewalls that operate on the TCP Layer 4 couldn't filter sites based on the URLs/Domains. For example, you cannot block `domain.com` or any of its subdomains by name. You need to know their IP addresses.  
This tool helps to get IP addresses for the given domain list and also tries to guess respective subdomains. It can be put behind a cron job that will regenerate the list and push it to the firewall.
Can be useful for Linux IpTables and Windows firewall.

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
```
usage: dns-guesser [-h] -d 'google.com,linkedin.com' [-s '8.8.8.8,8.8.4.4'] [-sw subdomain_list.txt] [-hc github.com] [-o dns_resolution_result.txt] [-fr]
                   [-t 64] [-db]

Subdomain Resolver

options:
  -h, --help            
  show this help message and exit
  
  -d 'google.com,linkedin.com', --domains-to-resolve 'google.com,linkedin.com'
  Comma-separated domains to resolve.
  
  -s '8.8.8.8,8.8.4.4', --dns-servers '8.8.8.8,8.8.4.4'
  Comma-separated list of DNS servers to use. Default is '8.8.8.8,8.8.4.4'.
  
  -sw subdomain_list.txt, --subdomain-word-list-file-path subdomain_list.txt
  Path to the subdomain word list file. If not provided, a default list with 5000 of the most used subdomains will be used.
  
  -hc github.com, --health-check-domain github.com
  Domain for the DNS servers health check. The DNS server is considered valid if it can resolve the domain. Default is 'github.com'.
  
  -o dns_resolution_result.txt, --output-file-path dns_resolution_result.txt
  Path to the result file. Default is './dns_resolution_result.txt'.
  
  -fr, --flat-result
  Writes results in flat format. Every line contains only an IP address. If not set, each domain will have its own section.
  
  -t 64, --max-thread-count 64
  Maximum number of threads to use. Default is 64.
  
  -db, --debug
  Outputs debug information.

Examples:
dns-guesser --domains-to-resolve "google.com, linkedin.com"
dns-guesser --domains-to-resolve "linkedin.com" --dns-servers "1.1.1.1" --subdomain-word-list-file-path ./subdomains.txt --health-check-domain github.com --output-file-path ./result.txt --flat-result False -t 100 --debug
```

Alternatively, you can put the configuration in a config file.
The application checks the config.json in the same working directory.
Example:
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
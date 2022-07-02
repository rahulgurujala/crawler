import csv
import re
import sys
from urllib.parse import urljoin, urlsplit

import requests
import requests.exceptions
from lxml import html

from extensions import garbage_extensions


class EmailCrawler:

    processed_urls = set()
    unprocessed_urls = set()
    emails = set()

    def __init__(self, website: str):
        self.website = website
        self.unprocessed_urls.add(website)
        self.headers = {
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/78.0.3904.70 Chrome/78.0.3904.70 Safari/537.36",
        }
        self.base_url = urlsplit(self.website).netloc
        self.outputfile = self.base_url.replace(".", "_") + ".csv"

        # we will use this list to skip urls that contain one of these extension.
        # This will save us a lot of bandwidth and speed up the crawling process
        # for example: www.example.com/image.png --> this url is useless for us.
        # we cannot possibly parse email from images and all other types of files.

        self.garbage_extensions = garbage_extensions
        self.email_count = 0

    def crawl(self):
        """
        It will continue crawling until the list unprocessed urls list is empty
        """

        url = self.unprocessed_urls.pop()
        print(f"CRAWL : {url}")
        self.parse_url(url)

        if len(self.unprocessed_urls) != 0:
            self.crawl()
        else:
            print(f"End of crawling for {self.website} ")
            print(f"Total urls visited {len(self.processed_urls)}")
            print(f"Total Emails found {self.email_count}")
            print(
                f'Dumping processed urls to {self.base_url.replace(".", "_") + ".txt"}'
            )
            with open(self.base_url.replace(".", "_") + ".txt", "w") as f:
                f.write("\n".join(self.processed_urls))

    def parse_url(self, current_url: str):
        """
        It will load and parse a given url. Loads it and finds all the url in this page.
        It also filters the urls and adds them to unprocessed url list.
        Finally it scrapes the emails if found on the page and the updates the email list

        INPUT:
            current_url: URL to parse
        RETURN:
            None
        """

        # we will retry to visit a url for 5 times in case it fails.
        # after that we will skip it in case if it still fails to load
        response = requests.get(current_url, headers=self.headers)
        tree = html.fromstring(response.content)
        urls = tree.xpath("//a/@href")  # getting all urls in the page

        # Here we will make sure that we convert the sub domain to full urls
        # example --> /about.html--> https://www.website.com/about.html
        urls = [urljoin(self.website, url) for url in urls]
        # now lets make sure that we only include the urls that fall under our domain
        # i.e filtering urls that point outside our main website.
        urls = [url for url in urls if self.base_url == urlsplit(url).netloc]

        # removing duplicates
        urls = list(set(urls))

        # filtering  urls that point to files such as images, videos and other as listed on garbage_extensions
        # Here will loop through all the urls and skip them if they contain one of the extension
        parsed_url = []
        for url in urls:
            skip = any(
                url.endswith(extension) or url.endswith(f"{extension}/")
                for extension in self.garbage_extensions
            )

            if not skip:
                parsed_url.append(url)

        # finally filtering urls that are already in queue or already visited
        for url in parsed_url:
            if url not in self.processed_urls and url not in self.unprocessed_urls:
                self.unprocessed_urls.add(url)

        # parsing email
        self.parse_emails(response.text)
        # adding the current url to processed list
        self.processed_urls.add(current_url)

    def parse_emails(self, text: str):
        """
        It scans the given texts to find email address and then writes them to csv
        Input:
            text: text to parse emails from
        Returns:
            bool: True or false (True if email was found on page)
        """
        # parsing emails and then saving to csv
        emails = set(
            re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text, re.I)
        )
        # TODO: sometime "gFJS3amhZEg_z39D5EErVg@2x.png" gets accepted as email with the above regex.
        # so for now i will check if email ends with jpeg,png and jpg

        for email in emails:
            skip_email = any(
                email.endswith(checker) for checker in ["jpg", "jpeg", "png"]
            )
            if not skip_email and email not in self.emails:
                with open(self.outputfile, "a", newline="") as csvf:
                    csv_writer = csv.writer(csvf)
                    csv_writer.writerow([email])
                self.email_count += 1
                self.emails.add(email)
                print(f" {self.email_count} Email found {email}")

        return len(emails) != 0


print("WELCOME TO EMAIL CRAWLER")
try:
    website = sys.argv[1]
except Exception:
    website = input("Please enter a website to crawl for emails:")
crawl = EmailCrawler(website)
crawl.crawl()

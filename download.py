
# Copyright (c) 2017 HH Partners, Attorneys-at-law Ltd
# SPDX-License-Identifier: Apache-2.0
# Author: Henri Tanskanen

from urllib.parse import urlparse
import codecs
import csv
from datetime import datetime
import xml.etree.ElementTree as etree
import hashlib
import json
import os
import re
import tarfile
import zipfile
from bs4 import BeautifulSoup   # outside std lib
import click                    # outside std lib
import requests                 # outside std lib


def validate_source_path(ctx, param, value):
    """ Check that source file is readable """
    if not os.access(value, os.R_OK):
        raise click.UsageError("No access to source file: " + value)
    else:
        return value


def get_txt_lines(fromfile):
    """ Get lines from file, strip empty ones, return list """
    try:
        with open(fromfile) as f:
            raw_lines = f.read().splitlines()
    except Exception as e:
        raise click.UsageError("Could not open the source file: " + str(e))
    lines = [r for r in raw_lines if len(r.strip()) > 0]
    return lines


def get_mvn_urls(fromfile):
    """
    Process Maven data in form: groupId;artifactId;version
    Check mvnrepository.com to see if indexed there, get download URL
    Return download URLs in list
    """
    lines = get_txt_lines(fromfile)
    click.echo("\nProcessing Maven data input...")
    lines = [line.split(';') for line in lines]
    mvn_urls = []
    for l in lines:
        if len(l) == 3:
            url_template = 'https://mvnrepository.com/artifact/{}/{}/{}'
            url = url_template.format(l[0], l[1], l[2])
            mvn_urls.append(url)
        else:
            click.echo("Malformed line in CSV:" + str(l))
    click.echo("Searching for download URLs on mvnrepository.com...")
    urls = []
    for murl in mvn_urls:
        try:
            content = requests.get(murl).content
            soup = BeautifulSoup(content, "html.parser")
            elements = soup.select("a.vbtn")
            for el in elements:
                if "Download (JAR)" in el.text or "Download (ZIP)" in el.text:
                    url = re.sub(r'\.(zip|jar)$', r'-sources.\1', el['href'])
                    if url:
                        urls.append(url)
                    else:
                        click.echo("No download link found on: " + murl)
        except requests.exceptions.RequestException as e:
            click.echo("Request error: " + str(e))
    return urls


def get_npm_license_info(file_path):
    """
    Inspect the package for package.json and possible license data there,
    return the license data (if any)
    """
    reader = codecs.getreader("utf-8")
    t = tarfile.open(file_path, 'r')
    try:
        f = t.extractfile('package/package.json')
    except:
        license = ""
        click.echo("Failed.")
        # logging?
    else:
        try:
            data = json.load(reader(f))
            license = data['license']
            click.echo("Success: " + license)
        except KeyError:
            license = ""
            click.echo("Failed (no license data in package.json?)")
        except:
            license = ""
            click.echo("Failed (error loading package.json data)")
            # logging
    return license


def get_mvn_license_info(url):
    """
    Try to extract license data from a POM file in the same repo folder
    as the source package, return the license data (if any)
    """
    pom_url = url.replace('-sources.jar', '.pom')
    try:
        response = requests.get(pom_url)
        tree = etree.ElementTree(etree.fromstring(response.text))
        root = tree.getroot()
        if root.tag[0] == "{":
            uri = root.tag[1:].split("}")[0]
            pre = "{" + uri + "}"
        else:
            pre = ""
        license_names = []
        for l in root.find(pre + 'licenses').findall(pre + 'license'):
            license_name = l.find(pre + 'name').text
            license_names.append(license_name)
        licenses_str = ", ".join(license_names)
        if len(licenses_str.strip()) > 0:
            license = licenses_str
            click.echo("Success: " + license)
        else:
            license = ""
            click.echo("Failed (no license data in POM?)")
    except:
        license = ""
        click.echo("Failed (POM license data not found or error)")
        # logging?
    return license


def get_file_hash(file_path):
    """ Get the file hash (SHA-1) """
    chunk_size = 65536
    hasher = hashlib.sha1()
    with open(file_path, 'rb') as f:
        buff = f.read(chunk_size)
        while len(buff) > 0:
            hasher.update(buff)
            buff = f.read(chunk_size)
    file_hash = hasher.hexdigest()
    return file_hash


@click.command()
@click.option('--directory',
              default='pkgs/',
              type=click.Path(writable=True),
              help="Destination download directory")
@click.option('--source',
              default='pkgs.txt',
              callback=validate_source_path,
              type=click.Path(readable=True),
              show_default=True,
              help="Path to file with the package list")
@click.option('--mvn',
              is_flag=True,
              help="Expect CSV input file: groupId;artifactId;version")
def cli(directory, mvn, source):
    """
    Download source packages based on list in file,
    print some info to CSV file (all.csv) in destination
    directory. Expects URL per row by default, alternatively
    searches mvnrepository.com based on Maven data (--mvn).
    """

    # Create target dir if doesn't exist
    try:
        os.makedirs(directory, exist_ok=True)   # Python >=3.2
    except Exception as e:
        raise click.BadParameter("Could not create directory/-ies: " +
                                 directory + " (" + str(e) + ")")
    dir_path = os.path.abspath(directory)

    # CSV output file related
    csv_name = 'all.csv'
    csv_path = dir_path + '/' + csv_name
    csv_mode = 'w'

    # Check if csv file exists
    if os.path.isfile(csv_path):
        if not os.access(csv_path, os.W_OK):
            raise click.UsageError("No access to " + csv_path)
        # Prompt how to deal with existing CSV output file
        while True:
            csv_mode = click.prompt("File '" + csv_name + "' already exists. "
                                    "Append/Overwrite/Cancel? [a/w/c]: ")
            if csv_mode not in set('awc'):
                click.echo("Please select [a/w/c]")
                continue
            else:
                break
    else:
        try:
            f = open(csv_path, 'w')
            f.close()
        except Exception as e:
            raise click.UsageError("No access to " + csv_path + " (" + str(e) + ")")

    if csv_mode == 'c':
        raise click.Abort

    # Produce the URL list from file
    if mvn:
        urls = get_mvn_urls(source)
    else:
        urls = get_txt_lines(source)

    # Download each URL and print to CSV, do some other stuff too

    csv_rows = []   # to store each csv row (as a dict)
    total = str(len(urls))
    bad_content = {'text/', 'application/json'}
    savefile_mode = None
    license_set = set()
    failed_list = []

    """
    <URL LOOP>
    """

    for index, url in enumerate(urls):

        parsed = urlparse(url)
        file_name = parsed.path.split('/')[-1]
        file_path = dir_path + '/' + file_name
        i = str(index + 1)

        if not savefile_mode and os.path.isfile(file_path):
            while True:
                savefile_mode = click.prompt("File (" + file_name + ") already"
                                             " exists. New/Overwrite/Skip?"
                                             " [n/w/s] (will be applied to "
                                             "ALL conflicts): ")
                if savefile_mode not in set('nws'):
                    click.echo("Please select [n/w/s]")
                    continue
                else:
                    break

        if savefile_mode == 'n':
            idx = 1
            alt_file_path = dir_path + "/(1) " + file_name
            while os.path.isfile(alt_file_path):
                idx += 1
                alt_file_path = dir_path + "/(" + str(idx) + ") " + file_name
            file_path = alt_file_path
            file_name = "(" + str(idx) + ") " + file_name

        elif savefile_mode == 's':
            click.echo("(" + i + "/" + total + ") Skipped: " + file_name)
            continue

        click.echo("(" + i + "/" + total + ") Downloading: " +
                   file_name, nl=False)

        try:
            response = requests.get(url, stream=True)
            time = str(datetime.now().strftime("%Y-%m-%d %H:%M"))
        except requests.exceptions.RequestException as e:
            click.echo(" ... FAILED: " + str(e))
            failed_list.append(url)
            continue

        content_type = response.headers['content-type']
        if any(bad in content_type for bad in bad_content):
            click.echo(" ... FAILED: Unexpected content-type (" +
                       content_type + "): " + url)
            failed_list.append(url)
            continue
        else:
            with open(file_path, "wb") as f:    # save the file
                for block in response.iter_content(65536):
                    f.write(block)

        if '://registry.npmjs.org/' in url:
            click.echo(" ... SUCCESS. Checking for license info...", nl=False)
            license = get_npm_license_info(file_path)
            if license:
                license_source = "package.json"
        elif mvn or re.search('-sources\.jar$', url):
            click.echo(" ... SUCCESS. Checking for license info...", nl=False)
            license = get_mvn_license_info(url)
            if license:
                license_source = "POM"
        else:
            license = ""
            if not tarfile.is_tarfile(file_path) and not zipfile.is_zipfile(file_path):
                click.echo(" ... SUCCESS but file not a zip/tar file?")
            else:
                click.echo(" ... SUCCESS.")
        if license:
            license_set.add(license)
        else:
            license_source = ""

        file_hash = get_file_hash(file_path)

        suffix = r'(?:-sources)?\.(?:tgz|zip|jar|tar|tar\.gz|gz|gem)$'
        component = re.sub(suffix, '', file_name)

        row = {
            'component': component,
            'url': url,
            'time': time,
            'sha1': file_hash,
            'file': file_name,
            'license_data': license,
            'license_data_src': license_source
        }
        csv_rows.append(row)

    """
    </URL LOOP>
    """

    finished = len(csv_rows)

    if finished > 0:
        click.echo("\nFinished: " + str(finished) + "/" + total +
                   " downloaded")
        click.echo("\nLicenses found (package.json / POM):")
        for lic in license_set:
            click.echo('\t' + lic)
        if failed_list:
            click.echo("\nFailed URLs:")
            for url in failed_list:
                click.echo(url)
        # Write to CSV
        fields = ['component', 'url', 'time', 'sha1', 'file', 'license_data', 'license_data_src']
        try:
            with open(csv_path, csv_mode, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields, dialect='excel', delimiter=";")
                if csv_mode == 'w':
                    writer.writeheader()
                writer.writerows(csv_rows)
        except PermissionError as e:
            click.echo("\nWRITE ERROR: No access to CSV file! " + str(e))
    else:
        click.echo("\nFinished without downloaded files.")
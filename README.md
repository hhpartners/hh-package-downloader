# hh-package-downloader
A simple command line utility for downloading source packages based on a list in a file, printing some info to a CSV file. At an early development stage.

## Installation
Intended for Python 3, tested with >= 3.5. Installation with pip recommended. A couple of dependencies are installed as part of the setup, so you may possibly want to use a [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/).
```
git clone https://github.com/hhpartners/hh-package-downloader.git
pip install hh-package-downloader
```
or if you want to keep editing the code, use ```pip install``` with the ```--editable``` flag.

## Use
After installation, the utility can be accessed with the ```hhdown``` command. For details, try ```hhdown --help```.

## Features
- Source packages are downloaded based on a list in a file (if not defined, looks for ```pkgs.txt``` in the same folder). 
- Supports input in two formats: (1) URL per row, or (2) when the ```--mvn``` flag is on, Maven data in CSV-style format: ```groupId;artifactId;version```. In the latter case, an attempt is made to find the correct repository and download URL via [MvnRepository.com](https://mvnrepository.com/). To be added: similar support for package info for packages hosted in the NPM Registry and RubyGems.org.
- For Maven packages, the utility will also try to extract license data from a POM file in the same repo folder as the source package. For packages downloaded from registry.npmjs.org, an attempt is made to find license data from the ```package.json``` file. To be added: similar support for license data in ```Rakefile``` and ```.gemspec``` files (in Ruby gems) and ```setup.py``` (Python packages).
- In addition to downloading the files, certain metadata is printed to a CSV file ```all.csv``` in the download target directory. Currently, this data is: component name and version, download URL, download timestamp, file hash (SHA-1), file name, license data (if any), source of license data.
- If the ```all.csv``` file already exists at the time of the download, the user is prompted whether to overwrite the file or append new lines. In case of file name conflicts for downloaded packages, the user is prompted whether to overwrite, skip or create a new file (with a different name).

## Limitations
- The file name for the downloaded file will be picked up from whatever follows the last ```/``` in the download URL, so only URLs like ```https://registry.npmjs.org/spdx/-/spdx-0.5.1.tgz``` are supported.
- The URL should lead directly to the package being served. If there's e.g. a web page in between where the user is expected to view ads, the download won't work.
- Only rudimentary checks (e.g. for content-type in HTTP response headers) are made to check whether the file being served is an actual source code package.

## Examples

### Most basic scenario
If you have your URLs (one per row) in a file named ```pkgs.txt```, you just have to run ```hhdown``` in that directory. A new subdirectory ```pkgs/``` will be created, and this is where the downloaded packages and ```all.csv``` will go.

### Bringing in some parameters
Downloading packages based on Maven data, specifying the paths to the input file and the output directory:
```
hhdown --mvn --source ../maven-package-data.csv --directory /home/henri/downloads/maven-test
```

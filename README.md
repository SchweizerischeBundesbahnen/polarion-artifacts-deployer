# Polarion artifacts deployer

## polarion-artifacts-deployer

This polarion-artifacts-deployer script is written to use jar files from Polarion delivery for Polarion extension development.
The script provides ability to install jars to local maven repository or deploy jars to SBB artifactory.

#### Supported parameters:

 - `--polarion-home` &mdash; path to folder where polarion is installed
 - `--action` &mdash; maven action: `install` to local repo or `deploy` to remote repo
 - `--repository-id` &mdash; if maven action `deploy` is used, repository id from maven settings.xml should be provided to use credentials for authentication
 - `--repository-url` &mdash; if maven action `deploy` is used, remote repository URL should be provided

#### Examples

To install to local maven repo:
```bash
polarion-artifacts-deployer.py --polarion-home C:\Polarion --action install
```
To deploy to remote maven repository:
```bash
polarion-artifacts-deployer.py --polarion-home C:\Polarion --action deploy --repository-id polarion.mvn --repository-url https://bin.sbb.ch/artifactory/polarion.mvn
```

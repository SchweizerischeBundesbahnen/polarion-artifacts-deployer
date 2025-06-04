#!/usr/bin/env python3

import argparse
import os
import sys
import tempfile
import textwrap

"""
# basic usage:
python ./polarion-artifacts-deployer.py --polarion-home <polarion_home> --polarion-version <version>
"""


def write_pom_file_content(pom_file, group_id, artifact_id, version):
    pom_content_template = '''<?xml version="1.0" encoding="UTF-8"?>
        <project xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd" xmlns="http://maven.apache.org/POM/4.0.0"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <modelVersion>4.0.0</modelVersion>
            <groupId>{group_id}</groupId>
            <artifactId>{artifact_id}</artifactId>
            <version>{version}</version>
            <description>POM was automatically created by polarion-artifact-deployer utility</description>
        </project>'''
    pom_content = textwrap.dedent(pom_content_template.format(**locals()))

    with open(pom_file, 'w') as output_file:
        output_file.write(pom_content)


def execute_mvn_command(mvn_action, file_name, group_id, artifact_id, version):
    separator()
    print(f'path       : {file_name}')
    print(f'groupId    : {group_id}')
    print(f'artifactId : {artifact_id}')
    print(f'version    : {version}')

    pom_file = tempfile.gettempdir() + os.sep + "pom.xml"
    write_pom_file_content(pom_file, group_id, artifact_id, version)

    mvn_command = f"mvn {mvn_action}:{mvn_action}-file -Dfile={file_name} -DgroupId={group_id} -DartifactId={artifact_id} -Dversion={version} -Dpackaging=jar -DgeneratePom=false -DpomFile={pom_file}"

    if args.settings_path:
        mvn_command += f' --settings {args.settings_path}'

    if args.repository_id:
        mvn_command += f' -DrepositoryId={args.repository_id}'

    if args.repository_url:
        mvn_command += f' -Durl={args.repository_url}'

    mvn_dependency_template = '''\
    <dependency>
        <groupId>{group_id}</groupId>
        <artifactId>{artifact_id}</artifactId>
        <version>{version}</version>
        <scope>provided</scope>
        <type>jar</type>
    </dependency>'''
    mvn_dependency = textwrap.dedent(mvn_dependency_template.format(**locals()))

    separator()
    print(mvn_command)

    try:
        exit_code = os.system(mvn_command)
        if exit_code > 0:
            sys.exit(exit_code % 255)
    finally:
        os.remove(pom_file)

    separator()
    print(mvn_dependency)
    separator()
    return mvn_dependency


def separator():
    print('-' * 20)


def process_bundles_folders(folder_names, version, jars_in_bundles_as_mvn_deps):
    for plugin_name in folder_names:
        print('handling ' + plugin_name + ' ...')
        plugin_name_tokens = plugin_name.split('_')
        group_id = plugin_name_tokens[0]
        process_jars_in_bundles_folders(plugin_name, group_id, version, jars_in_bundles_as_mvn_deps)


def process_jars_in_bundles_folders(plugin_name, group_id, version, jars_in_bundles_as_mvn_deps):
    polarion_plugin_path = polarion_plugins_path + os.sep + plugin_name
    for entry_name in os.listdir(polarion_plugin_path):
        if entry_name.endswith('.jar'):
            jar_path = polarion_plugin_path + os.sep + entry_name
            artifact_id = entry_name[0: len(entry_name) - 4]
            mvn_dep = execute_mvn_command(args.mvn_action, jar_path, group_id, artifact_id, version)
            jars_in_bundles_as_mvn_deps.append(mvn_dep)


def process_bundles_jars(jar_names, version, bundles_as_mvn_deps):
    for jar_name in jar_names:
        artifact_id = jar_name.removesuffix('.jar')
        jar_path = polarion_plugins_path + os.sep + jar_name
        mvn_dep = execute_mvn_command(args.mvn_action, jar_path, 'com.polarion.thirdparty', artifact_id, version)
        bundles_as_mvn_deps.append(mvn_dep)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='install or deploy Polarion artifacts to maven repository')
    parser.add_argument('--polarion-home', metavar='path', required=True, dest='polarion_home', action='store', help='Polarion installation folder')
    parser.add_argument('--polarion-version', metavar='version', required=True, dest='polarion_version', action='store', help='Polarion version')
    parser.add_argument('--action', dest='mvn_action', action='store', choices={'install', 'deploy'}, default='install', help='maven action')
    parser.add_argument('--settings-path', metavar='path', dest='settings_path', help='path to settings.xml')
    parser.add_argument('--repository-id', metavar='repo', dest='repository_id', action='store', help='repository id from maven settings.xml')
    parser.add_argument('--repository-url', metavar='url', dest='repository_url', action='store', help='repository URL to deploy the artifacts')

    args = parser.parse_args()

    print('polarion home = ' + args.polarion_home)
    print('polarion version = ' + args.polarion_version)
    polarion_plugins_path = args.polarion_home + os.sep + 'polarion' + os.sep + 'plugins'
    print('polarion plugins path = ' + polarion_plugins_path)
    print('mvn action = ' + args.mvn_action)

    plugins_bundles = []
    polarion_jars = []

    for root, folders, files in os.walk(polarion_plugins_path):
        for folder in folders:
            plugins_bundles.append(folder)
        for file in files:
            if file.endswith('.jar'):
                polarion_jars.append(file)
        break

    print('following polarion bundles detected = ', plugins_bundles)
    print()
    print('following polarion jars detected = ', polarion_jars)
    print()

    bundles_mvn_deps = []
    jars_in_bundles_mvn_deps = []

    process_bundles_folders(plugins_bundles, args.polarion_version, jars_in_bundles_mvn_deps)
    process_bundles_jars(polarion_jars, args.polarion_version, bundles_mvn_deps)
    print('####################################')
    print('Runtime platform maven dependencies:')
    print('####################################')
    print(os.linesep.join(bundles_mvn_deps))
    print('####################################')

    print('************************************')
    print('Compile platform maven dependencies:')
    print('************************************')
    print(os.linesep.join(jars_in_bundles_mvn_deps))
    print('************************************')

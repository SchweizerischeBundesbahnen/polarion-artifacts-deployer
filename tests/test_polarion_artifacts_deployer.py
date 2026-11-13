import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / 'polarion-artifacts-deployer' / 'polarion-artifacts-deployer.py'

# The file name has hyphens, so a plain import cannot load it.
_spec = importlib.util.spec_from_file_location('polarion_artifacts_deployer', SCRIPT)
deployer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deployer)

MVN = '/opt/maven/bin/mvn'


def deployer_args(settings_path=None, repository_id=None, repository_url=None, mvn_action='install'):
    return argparse.Namespace(settings_path=settings_path, repository_id=repository_id,
                              repository_url=repository_url, mvn_action=mvn_action)


class DeployerTestCase(unittest.TestCase):
    """Runs the script functions against a temporary directory, with mvn and its lookup mocked."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_dir = Path(temp_dir.name)
        self.pom_file = self.temp_dir / 'pom.xml'

        self.patch(deployer.tempfile, 'gettempdir', return_value=str(self.temp_dir))
        self.which = self.patch(deployer.shutil, 'which', return_value=MVN)
        self.run = self.patch(deployer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0))
        self.patch(deployer, 'args', new=deployer_args(), create=True)
        self.patch(sys, 'stdout', new_callable=mock.MagicMock)

    def patch(self, target, attribute, **kwargs):
        patcher = mock.patch.object(target, attribute, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def mvn_command(self, call_index=0):
        return self.run.call_args_list[call_index].args[0]


class ExecuteMvnCommandTest(DeployerTestCase):

    def test_passes_every_coordinate_as_one_argument(self):
        deployer.execute_mvn_command('install', '/polarion home/plugins/core.jar', 'com.polarion', 'core', '2606')

        self.assertEqual([MVN, 'install:install-file', '-Dfile=/polarion home/plugins/core.jar',
                          '-DgroupId=com.polarion', '-DartifactId=core', '-Dversion=2606', '-Dpackaging=jar',
                          '-DgeneratePom=false', f'-DpomFile={self.pom_file}'], self.mvn_command())

    def test_runs_without_a_shell(self):
        deployer.execute_mvn_command('install', 'core.jar', 'com.polarion', 'core', '2606')

        self.assertNotIn('shell', self.run.call_args.kwargs)

    def test_uses_the_deploy_goal_for_deploy(self):
        deployer.execute_mvn_command('deploy', 'core.jar', 'com.polarion', 'core', '2606')

        self.assertEqual('deploy:deploy-file', self.mvn_command()[1])

    def test_adds_the_settings_and_repository_options(self):
        deployer.args = deployer_args(settings_path='/my settings.xml', repository_id='private',
                                      repository_url='https://repo.example.com/maven')

        deployer.execute_mvn_command('deploy', 'core.jar', 'com.polarion', 'core', '2606')

        self.assertEqual(['--settings', '/my settings.xml', '-DrepositoryId=private',
                          '-Durl=https://repo.example.com/maven'], self.mvn_command()[-4:])

    def test_returns_the_dependency_xml(self):
        dependency = deployer.execute_mvn_command('install', 'core.jar', 'com.polarion', 'core', '2606')

        self.assertEqual('<dependency>\n'
                         '    <groupId>com.polarion</groupId>\n'
                         '    <artifactId>core</artifactId>\n'
                         '    <version>2606</version>\n'
                         '    <scope>provided</scope>\n'
                         '    <type>jar</type>\n'
                         '</dependency>', dependency)

    def test_writes_the_pom_that_mvn_reads(self):
        pom_contents = []
        self.run.side_effect = lambda command, **kwargs: (pom_contents.append(self.pom_file.read_text()),
                                                          subprocess.CompletedProcess(command, 0))[1]

        deployer.execute_mvn_command('install', 'core.jar', 'com.polarion', 'core', '2606')

        self.assertIn('<groupId>com.polarion</groupId>', pom_contents[0])
        self.assertIn('<artifactId>core</artifactId>', pom_contents[0])
        self.assertIn('<version>2606</version>', pom_contents[0])

    def test_removes_the_pom_after_a_success(self):
        deployer.execute_mvn_command('install', 'core.jar', 'com.polarion', 'core', '2606')

        self.assertFalse(self.pom_file.exists())

    def test_exits_with_the_return_code_of_mvn(self):
        self.run.return_value = subprocess.CompletedProcess([], 3)

        with self.assertRaises(SystemExit) as raised:
            deployer.execute_mvn_command('install', 'core.jar', 'com.polarion', 'core', '2606')

        self.assertEqual(3, raised.exception.code)

    def test_removes_the_pom_after_a_failure(self):
        self.run.return_value = subprocess.CompletedProcess([], 1)

        with self.assertRaises(SystemExit):
            deployer.execute_mvn_command('install', 'core.jar', 'com.polarion', 'core', '2606')

        self.assertFalse(self.pom_file.exists())


class MvnExecutableTest(DeployerTestCase):

    def test_returns_mvn_from_the_path(self):
        self.assertEqual(MVN, deployer.mvn_executable())

    def test_exits_when_mvn_is_not_on_the_path(self):
        self.which.return_value = None

        with self.assertRaises(SystemExit) as raised:
            deployer.mvn_executable()

        self.assertEqual('mvn not found on PATH', raised.exception.code)


class PluginsTest(DeployerTestCase):

    def setUp(self):
        super().setUp()
        self.plugins = self.temp_dir / 'polarion' / 'plugins'
        self.plugins.mkdir(parents=True)
        self.patch(deployer, 'polarion_plugins_path', new=str(self.plugins), create=True)

    def test_deploys_the_jars_of_a_bundle_under_the_group_of_the_bundle(self):
        bundle = self.plugins / 'com.polarion.core_3.26.6'
        bundle.mkdir()
        (bundle / 'core.jar').touch()
        (bundle / 'readme.txt').touch()
        dependencies = []

        deployer.process_bundles_folders(['com.polarion.core_3.26.6'], '2606', dependencies)

        self.assertEqual(1, self.run.call_count)
        self.assertIn('-DgroupId=com.polarion.core', self.mvn_command())
        self.assertIn('-DartifactId=core', self.mvn_command())
        self.assertEqual(1, len(dependencies))

    def test_deploys_a_jar_in_plugins_as_a_thirdparty_artifact(self):
        dependencies = []

        deployer.process_bundles_jars(['library.jar'], '2606', dependencies)

        self.assertIn(f'-Dfile={self.plugins}{os.sep}library.jar', self.mvn_command())
        self.assertIn('-DgroupId=com.polarion.thirdparty', self.mvn_command())
        self.assertIn('-DartifactId=library', self.mvn_command())
        self.assertEqual(1, len(dependencies))


class CommandLineTest(unittest.TestCase):
    """Runs the script as a process, for the checks that happen before any mvn call."""

    def run_script(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False)

    def test_rejects_a_version_with_shell_characters(self):
        result = self.run_script('--polarion-home', '/nowhere', '--polarion-version', '2606; touch /tmp/x')

        self.assertEqual(2, result.returncode)
        self.assertIn('invalid Polarion version', result.stderr)

    def test_rejects_a_version_that_looks_like_an_option(self):
        result = self.run_script('--polarion-home', '/nowhere', '--polarion-version=-Dfoo')

        self.assertEqual(2, result.returncode)
        self.assertIn('invalid Polarion version', result.stderr)

    def test_accepts_a_version_with_a_build_suffix(self):
        with tempfile.TemporaryDirectory() as polarion_home:
            result = self.run_script('--polarion-home', polarion_home, '--polarion-version', '2410-1.0_rc')

        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()

"""
Integration tests for containerized deployment
Tests the container configuration files and quadlet setup
"""
import os
import subprocess
import pytest
import yaml
import configparser

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDockerComposeConfig:
    """Test container compose configuration"""

    @staticmethod
    def get_compose_path():
        return os.path.join(REPO_DIR, 'container-compose.yml')
    
    def test_compose_file_exists(self):
        compose_path = self.get_compose_path()
        assert os.path.exists(compose_path)
        legacy_path = os.path.join(REPO_DIR, 'docker-compose.yml')
        assert os.path.islink(legacy_path)
    
    def test_compose_file_valid_yaml(self):
        compose_path = self.get_compose_path()
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        
        assert 'services' in config
        assert 'tor' in config['services']
        assert 'opsechat' in config['services']
    
    def test_compose_services_have_required_config(self):
        compose_path = self.get_compose_path()
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        
        # Tor service checks
        tor_service = config['services']['tor']
        assert 'image' in tor_service
        assert 'volumes' in tor_service
        assert 'networks' in tor_service
        
        # Opsechat service checks
        opsechat_service = config['services']['opsechat']
        assert 'build' in opsechat_service
        assert 'depends_on' in opsechat_service
        assert 'environment' in opsechat_service
        assert 'healthcheck' in opsechat_service
        assert 'networks' in opsechat_service
    
    def test_compose_network_isolation(self):
        """Verify services use isolated network"""
        compose_path = self.get_compose_path()
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        
        assert 'networks' in config
        assert 'opsechat-network' in config['networks']
        
        # Both services should use the same network
        assert 'opsechat-network' in config['services']['tor']['networks']
        assert 'opsechat-network' in config['services']['opsechat']['networks']
    
    def test_compose_no_ports_exposed_by_default(self):
        """Verify no ports are exposed to host by default"""
        compose_path = self.get_compose_path()
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        
        # Tor should not expose ports
        tor_service = config['services']['tor']
        assert 'ports' not in tor_service or not tor_service['ports']
        
        # Opsechat should not expose ports (might be commented out)
        opsechat_service = config['services']['opsechat']
        assert 'ports' not in opsechat_service or not opsechat_service['ports']

    def test_compose_app_healthcheck_targets_local_health_endpoint(self):
        compose_path = os.path.join(REPO_DIR, 'docker-compose.yml')
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        healthcheck = config['services']['opsechat']['healthcheck']
        assert healthcheck['test'] == [
            'CMD', 'curl', '--fail', '--silent', 'http://127.0.0.1:5000/health'
        ]


class TestDockerfile:
    """Test Dockerfile configuration"""

    @staticmethod
    def get_dockerfile_path():
        return os.path.join(REPO_DIR, 'containers', 'Dockerfile')
    
    def test_dockerfile_exists(self):
        dockerfile_path = self.get_dockerfile_path()
        assert os.path.exists(dockerfile_path)
        assert os.path.islink(os.path.join(REPO_DIR, 'Dockerfile'))
    
    def test_dockerfile_uses_python_base(self):
        dockerfile_path = self.get_dockerfile_path()
        with open(dockerfile_path) as f:
            content = f.read()
        
        assert 'FROM python:' in content
    
    def test_dockerfile_installs_dependencies(self):
        dockerfile_path = self.get_dockerfile_path()
        with open(dockerfile_path) as f:
            content = f.read()
        
        assert 'pip install' in content
        assert 'requirements.txt' in content

    def test_dockerfile_has_healthcheck(self):
        dockerfile_path = os.path.join(REPO_DIR, 'Dockerfile')
        with open(dockerfile_path) as f:
            content = f.read()

        assert 'HEALTHCHECK' in content
        assert '/health' in content
    
    def test_dockerfile_copies_app_files(self):
        dockerfile_path = self.get_dockerfile_path()
        with open(dockerfile_path) as f:
            content = f.read()
        
        # Key app files should be copied
        assert 'runserver.py' in content
        assert 'COPY *.py ./' in content
        assert 'templates/' in content


class TestTorConfig:
    """Test Tor configuration"""

    @staticmethod
    def get_torrc_path():
        return os.path.join(REPO_DIR, 'containers', 'torrc')
    
    def test_torrc_exists(self):
        torrc_path = self.get_torrc_path()
        assert os.path.exists(torrc_path)
        assert os.path.islink(os.path.join(REPO_DIR, 'torrc'))
    
    def test_torrc_has_control_port(self):
        torrc_path = self.get_torrc_path()
        with open(torrc_path) as f:
            content = f.read()
        
        assert 'ControlPort 9051' in content
    
    def test_torrc_has_cookie_auth(self):
        torrc_path = self.get_torrc_path()
        with open(torrc_path) as f:
            content = f.read()
        
        assert 'CookieAuthentication' in content


class TestQuadletFiles:
    """Test Podman Quadlet configuration files"""
    
    def get_quadlet_path(self, filename):
        return os.path.join(REPO_DIR, 'quadlets', filename)
    
    def test_quadlets_directory_exists(self):
        quadlets_dir = os.path.join(REPO_DIR, 'quadlets')
        assert os.path.isdir(quadlets_dir)
    
    def test_network_quadlet_exists(self):
        assert os.path.exists(self.get_quadlet_path('opsechat.network'))
    
    def test_volume_quadlet_exists(self):
        assert os.path.exists(self.get_quadlet_path('tor-data.volume'))
    
    def test_tor_container_quadlet_exists(self):
        assert os.path.exists(self.get_quadlet_path('opsechat-tor.container'))
    
    def test_app_container_quadlet_exists(self):
        assert os.path.exists(self.get_quadlet_path('opsechat-app.container'))
    
    def test_network_quadlet_has_required_sections(self):
        path = self.get_quadlet_path('opsechat.network')
        config = configparser.ConfigParser()
        config.read(path)
        
        assert 'Unit' in config.sections()
        assert 'Network' in config.sections()
    
    def test_container_quadlet_has_required_sections(self):
        """Test that quadlet files have required sections.
        
        Note: Quadlet files can have duplicate keys (valid for systemd),
        so we check by parsing the file content directly instead of using
        configparser which doesn't allow duplicates.
        """
        required_sections = ['[Unit]', '[Container]', '[Service]', '[Install]']
        
        for quadlet in ['opsechat-tor.container', 'opsechat-app.container']:
            path = self.get_quadlet_path(quadlet)
            with open(path) as f:
                content = f.read()
            
            for section in required_sections:
                assert section in content, f"{quadlet} missing {section} section"
    
    def test_app_container_depends_on_tor(self):
        path = self.get_quadlet_path('opsechat-app.container')
        with open(path) as f:
            content = f.read()
        
        assert 'After=opsechat-tor' in content
        assert 'Requires=opsechat-tor' in content
    
    def test_containers_use_same_network(self):
        for quadlet in ['opsechat-tor.container', 'opsechat-app.container']:
            path = self.get_quadlet_path(quadlet)
            with open(path) as f:
                content = f.read()
            
            assert 'Network=opsechat-network' in content, \
                f"{quadlet} should use opsechat-network"
    
    def test_app_container_no_ports_exposed(self):
        """Verify ports are not exposed by default (may be commented)"""
        path = self.get_quadlet_path('opsechat-app.container')
        with open(path) as f:
            lines = f.readlines()
        
        # Check that PublishPort line is commented out
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('PublishPort='):
                pytest.fail("PublishPort should be commented out by default")


class TestScripts:
    """Test helper scripts"""

    def assert_script_location(self, filename):
        script_path = os.path.join(REPO_DIR, 'scripts', filename)
        assert os.path.exists(script_path)
        assert os.access(script_path, os.X_OK)
        legacy_path = os.path.join(REPO_DIR, filename)
        assert os.path.islink(legacy_path)
    
    def test_compose_up_script_exists(self):
        self.assert_script_location('compose-up.sh')
    
    def test_compose_down_script_exists(self):
        self.assert_script_location('compose-down.sh')
    
    def test_verify_setup_script_exists(self):
        self.assert_script_location('verify-setup.sh')
    
    def test_install_quadlets_script_exists(self):
        self.assert_script_location('install-quadlets.sh')

    def test_compose_status_script_exists(self):
        self.assert_script_location('compose-status.sh')


class TestReleaseSkeleton:
    """Test the requested release layout exists."""

    def test_release_directories_exist(self):
        for directory in ['src', 'include', 'containers', 'quadlets', 'tests', 'docs']:
            path = os.path.join(REPO_DIR, directory)
            assert os.path.isdir(path), f"{directory} should exist"

    def test_release_files_exist(self):
        for filename in ['container-compose.yml', 'install.sh', 'Pfyfile.pf']:
            path = os.path.join(REPO_DIR, filename)
            assert os.path.exists(path), f"{filename} should exist"


class TestDocumentation:
    """Test documentation files exist"""
    
    def test_docker_md_exists(self):
        path = os.path.join(REPO_DIR, 'DOCKER.md')
        assert os.path.exists(path)
    
    def test_quadlets_md_exists(self):
        path = os.path.join(REPO_DIR, 'QUADLETS.md')
        assert os.path.exists(path)
    
    def test_domain_registrar_api_md_exists(self):
        path = os.path.join(REPO_DIR, 'DOMAIN_REGISTRAR_API.md')
        assert os.path.exists(path)
    
    def test_readme_mentions_docker(self):
        path = os.path.join(REPO_DIR, 'README.md')
        with open(path) as f:
            content = f.read()
        
        assert 'Docker' in content or 'docker' in content
        assert 'compose-up.sh' in content or 'DOCKER.md' in content

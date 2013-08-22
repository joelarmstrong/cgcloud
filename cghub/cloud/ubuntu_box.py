import contextlib
import csv
import textwrap
import urllib2
from fabric.operations import sudo, run
import yaml
from box import fabric_task
from cghub.cloud.unix_box import UnixBox

BASE_URL = 'http://cloud-images.ubuntu.com'


class TemplateDict( dict ):
    def matches(self, other):
        return all( v == other.get( k ) for k, v in self.iteritems( ) )


class UbuntuBox( UnixBox ):
    """
    A box representing EC2 instances that boot from one of Ubuntu's cloud-image AMIs
    """

    def release(self):
        """
        :return: the code name of the Ubuntu release, e.g. "precise"
        """
        raise NotImplementedError( )

    def __init__(self, env):
        super( UbuntuBox, self ).__init__( env )
        release = self.release( )
        self._log( "Looking up AMI for Ubuntu release %s ..." % release, newline=False )
        self.base_image = self.__find_image(
            template=TemplateDict( release=release,
                                   purpose='server',
                                   release_type='release',
                                   storage_type='ebs',
                                   arch='amd64',
                                   region=env.region,
                                   hypervisor='paravirtual' ),
            url='%s/query/%s/server/released.current.txt' % ( BASE_URL, release ),
            fields=[
                'release', 'purpose', 'release_type', 'release_date',
                'storage_type', 'arch', 'region', 'ami_id', 'aki_id',
                'dont_know', 'hypervisor' ] )
        self._log( ", found %s." % self.image_id( ) )

    @staticmethod
    def __find_image(template, url, fields):
        matches = [ ]
        with contextlib.closing( urllib2.urlopen( url ) ) as stream:
            images = csv.DictReader( stream, fields, delimiter='\t' )
            for image in images:
                if template.matches( image ):
                    matches.append( image )
        if len( matches ) < 1:
            raise RuntimeError( 'No matching images' )
        if len( matches ) > 1:
            raise RuntimeError( 'More than one matching images: %s' % matches )
        match = matches[ 0 ]
        return match

    def username(self):
        return 'ubuntu'

    def image_id(self):
        return self.base_image[ 'ami_id' ]

    def setup(self, upgrade_installed_packages=False):
        self.__wait_for_cloud_init_completion( )
        super( UbuntuBox, self ).setup( upgrade_installed_packages )

    def user_data(self):
        user_data = { }
        self._populate_cloud_config( user_data )
        if user_data:
            return '#cloud-config\n' + yaml.dump( user_data )
        else:
            return None

    def _populate_cloud_config(self, user_data):
        # see __wait_for_cloud_init_completion()
        #
        user_data.setdefault( 'runcmd', [] ).append( [ 'touch', '/tmp/cloud-init.done' ] )

        # Lucid's and Oneiric's cloud-init mount ephemeral storage on /mnt instead of
        # /mnt/ephemeral. To keep it consistent across releases we should be explicit.
        #
        user_data.setdefault( 'mounts', [ ] ).append(
            [ 'ephemeral0', '/mnt/ephemeral', 'auto', 'defaults,nobootwait' ] )


    @fabric_task
    def __wait_for_cloud_init_completion(self):
        """
        Wait for Ubuntu's cloud-init to finish its job such as to avoid getting in its way.
        Without this, I've seen weird errors with 'apt-get install' not being able to find any
        packages.
        """
        # /var/lib/cloud/instance/boot-finished isn't being written all releases, e.g. Lucid. Must
        # use our own file create by a runcmd, see user_data()
        run( 'echo -n "Waiting for cloud-init to finish ..." ; '
             'while [ ! -e /tmp/cloud-init.done ]; do '
             'echo -n "."; '
             'sleep 1; '
             'done; '
             'echo ", done."' )

    apt_get = 'DEBIAN_FRONTEND=readline apt-get -q -y'

    @fabric_task
    def _sync_package_repos(self):
        sudo( '%s update' % self.apt_get )

    @fabric_task
    def _upgrade_installed_packages(self):
        sudo( '%s upgrade' % self.apt_get )

    @fabric_task
    def _install_packages(self, packages):
        packages = " ".join( packages )
        sudo( '%s install %s' % (self.apt_get, packages ) )

    @fabric_task
    def _debconf_set_selection(self, *debconf_selections):
        for debconf_selection in debconf_selections:
            if '"' in debconf_selection:
                raise RuntimeError( 'Doubles quotes in debconf selections are not supported yet' )
        sudo( 'debconf-set-selections <<< "%s"' % '\n'.join( debconf_selections ) )


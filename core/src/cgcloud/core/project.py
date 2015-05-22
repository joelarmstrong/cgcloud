import glob
import os
import warnings

from pkginfo import Installed


def project_artifacts( project_name ):
    """
    Similar to project_artifact but including dependent project artifacts
    """
    # FIXME: This is a bit simplistic
    if project_name == 'lib':
        return [ project_artifact( project_name ) ]
    else:
        return [ project_artifact( 'lib' ), project_artifact( project_name ) ]


def project_artifact( project_name ):
    """
    Resolve the name of a sibling project to something that can be passed to pip in order to get
    that project installed. The version of the sibling project is assumed to be identical to the
    currently installed version of this project (cgcloud-core). If the version can't be
    determined, a source distribution is looked up in the 'dist' subdirectory of the sibling
    project. This is likely to be the case in development mode, i.e. if this project was
    installed via 'setup.py develop'. If neither version nor source distribution can be
    determined, an exception will be raised.

    :param project_name: the name of a sibling project such as 'agent' or 'spark-tools'

    :return: Either an absolute path to a source distribution or a requirement specifier to be
    looked up in the Python package index (PyPI).
    """
    with warnings.catch_warnings( ):
        warnings.simplefilter( "ignore" )
        version = Installed( __name__ ).version
    if version is None:
        dir_path = os.path.dirname( os.path.abspath( __file__ ) )
        while not os.path.exists( os.path.join( dir_path, 'setup.py' ) ):
            parent_dir_path = os.path.dirname( dir_path )
            if parent_dir_path == dir_path:
                raise RuntimeError( "Couldn't find parent directory" )
            dir_path = parent_dir_path
        project_path = os.path.join( os.path.dirname( dir_path ), project_name )
        sdist_glob = os.path.join( project_path, 'dist', 'cgcloud-%s*.tar.gz' % project_name )
        sdist = glob.glob( sdist_glob )
        if len( sdist ) == 1:
            sdist = sdist[ 0 ]
        elif sdist:
            raise RuntimeError(
                "Can't decide which of these is the '%s' source distribution: %s" % (
                    project_name, sdist ) )
        else:
            raise RuntimeError( "Can't find '%s' source distribution. Looking for '%s'." % (
                project_name, sdist_glob ) )
        return sdist
    else:
        return 'cgcloud-%s==%s' % ( project_name, version )

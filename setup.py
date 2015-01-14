from setuptools import setup, find_packages
import os

version = '1.0'

setup(name='collective.geo.mapview',
      version=version,
      description="Map View for Plone Maps",
      long_description=open("README.rst").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.rst")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "Framework :: Plone",
        "Programming Language :: Python",
        ],
      keywords='ushahidi plone maps geo kml',
      author='marr',
      author_email='marr.tw@gmail.com',
      url='http://github.com/l34marr/collective.geo.mapview',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['collective', 'collective.geo'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'Products.AdvancedQuery',
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-

      [z3c.autoinclude.plugin]
      target = plone
      """,
      )

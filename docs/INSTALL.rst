collective.geo.mapview Installation
===================================

To install collective.geo.mapview using zc.buildout and
the plone.recipe.zope2instance recipe to manage your project,
you can do this:

 * Add ``collective.geo.mapview`` to the list of eggs to install, e.g.:

    [buildout]
    ...
    eggs =
        ...
        collective.geo.bundle [dexterity]
        collective.geo.mapview

 * Tell the plone.recipe.zope2instance recipe to install a ZCML slug:

    [instance]
    recipe = plone.recipe.zope2instance
    ...
    zcml =
        collective.geo.mapview

 * Re-run buildout, e.g. with:

    $ ./bin/buildout

You can skip the ZCML slug if you are going to explicitly include the package
from another package's configure.zcml file.


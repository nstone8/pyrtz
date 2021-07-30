def get_equivalent_diameter_sphere_on_sphere(d_probe,d_cell):
    '''Hertzian contact between to spheres is the 
    same as that between a sphere and a half space
    (the fit done by pyrtz.curves.Curve.fit_stiffness)
    but with a modified probe diameter. This function
    calculates that 'effective diameter'

    https://en.wikipedia.org/wiki/Contact_mechanics#Contact_between_two_spheres

    --------------------Arguments--------------------

    d_probe: Probe diameter

    d_cell: Cell diameter

    ---------------------Returns---------------------

    The 'effective diameter' of this interaction'''

    r_probe=d_probe/2
    r_cell=d_cell/2

    r_inv=(1/r_probe)+(1/r_cell)

    return 2*(1/r_inv)

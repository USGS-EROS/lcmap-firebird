from firebird import ccd_params
from firebird import products as fp
from functools import partial
from functools import wraps
from merlin import chips
from merlin import dates
from merlin import functions as f
from merlin import timeseries
import ccd
import merlin


def algorithm(name, version):
    """Standardizes algorithm name and version representation.

    Args:
        name (str): Algorithm name
        version (str): Algorithm version

    Returns:
        str: name_version
    """

    return '{}_{}'.format(name, version)


def success(chip_x, chip_y, x, y, alg, datestr, result):
    """Formats an rdd transformation result.

    Args:
        chip_x (float): x coordinate of source chip id
        chip_y (float): y coordinate of source chip id
        x (float): x coordinate
        y (float): y coordinate
        alg (str): algorithm and version string
        datestr (str): datestr that identifies the result
        result (str): algorithm outputs

    Returns:
        tuple: ((chip_x, chip_y, x, y, alg, datestr), result, 0)
    """

    return ((chip_x, chip_y, x, y, alg, datestr), result, 0)


def error(chip_x, chip_y, x, y, alg, datestr, errors):
    """Format an rdd transformation error

    Args:
        chip_x (float): x coordinate of source chip id
        chip_y (float): y coordinate of source chip id
        x (float): x coordinate
        y (float): y coordinate
        alg (str): algorithm and version string
        datestr (str): datestr that identifies the result
        errors (str): algorithm errors

    Returns:
        tuple: ((chip_x, chip_y, x, y, alg, datestr), None, errors)
    """

    return ((chip_x, chip_y, x, y, alg, datestr), errors, 1)


def haserrors(chip_x, chip_y, x, y, alg, datestr, errors):
    """Determines if previous errors exist and creates proper return value
    if True.  If no error exists returns False.

    Args:
        chip_x (float): x coordinate of source chip id
        chip_y (float): y coordinate of source chip id
        x (float): x coordinate
        y (float): y coordinate
        alg (str): algorithm and version string
        datestr (str): datestr for current RDD record
        errs (str): Errors element from input RDD

    Returns:
        False or tuple: Either False if no errors or an error()
    """

    if errors is None:
        return False
    else:
        e = 'previous-error:{}'.format(errors)
        return error(chip_x=chip_x, chip_y=chip_y, x=x, y=y, alg=alg,
                     datestr=datestr, errors=e)


def tryexcept(func, kwargs, chip_x, chip_y, x, y, alg, datestr):
    """Executes a function wrapped in try: except:.  Returns result
    of success() or error().

    Args:
        func (func): function to execute
        kwargs (dict): keyword args for func
        chip_x (float): x coordinate of source chip id
        chip_y (float): y coordinate of source chip id
        x (float): x coordinate
        y (float): y coordinate
        alg (str): algorithm and version string
        datestr (str): date string that identifies this execution

    Returns:
        tuple: value of success() or error()
    """

    try:
        return success(chip_x=chip_x, chip_y=chip_y, x=x, y=y, alg=alg,
                       datestr=datestr, result=func(**kwargs))
    except Exception as errs:
        return error(chip_x=chip_x, chip_y=chip_y, x=x, y=y, alg=alg,
                     datestr=datestr, errors=errs)


def safely(func, kwargs, chip_x, chip_y, x, y, alg, datestr, errors):
    """Runs a function for an input with exception handling applied

    Args:
     func (func): function to execute
     kwargs (dict): keyword args for func
     chip_x (float): x coordinate of source chip id
     chip_y (float): y coordinate of source chip id
     x (float): x coordinate
     y (float): y coordinate
     alg (str): algorithm and version string
     datestr (str): date string that identifies this execution
     errors (str): value of input rdd tuple position for errors.

    Returns:
        tuple: value of success() or error()
    """

    return (haserrors(chip_x=chip_x, chip_y=chip_y, x=x, y=y, alg=alg,
                      datestr=datestr, errors=errors) or
            tryexcept(func=func, kwargs=kwargs, chip_x=chip_x, chip_y=chip_y,
                      x=x, y=y, alg=alg, datestr=datestr))


def ccdresults_to_dict(results):
    """Convert child objects inside CCD results from NamedTuples to dicts

    Args:
        results (dict): pyccd results

    Returns:
        dict: pyccd results with namedtuples converted to dicts
    """

    def simplify(result):
        return {k: f.simplify_objects(v) for k, v in result.items()}

    return simplify(results) if type(results) is dict else dict()


def result_to_models(result):
    """Function to extract the change_models dictionary from the CCD results

    Args:
        result (dict): CCD result object

    Returns:
       dict: ccd result with nametuples converted to dicts
    """

    return ccdresults_to_dict(result).get('change_models')


def pyccd(rdd):
    """Execute ccd.detect

    Args:
        rdd (rdd): Tuple of (tuple, dict) generated from pyccd_inputs
                   ((chip_x, chip_y, x, y, algorithm, datestring), data, errors)

    Returns:
        tuple: tuple of (tuple, dict) with pyccd results
               ((chip_x, chip_y, x, y, algorithm, acquired), results, errors)
    """

    chip_x = rdd[0][0]
    chip_y = rdd[0][1]
    x = rdd[0][2]
    y = rdd[0][3]
    acquired = rdd[0][5]
    data = rdd[1] or dict()
    errs = rdd[2]
    kwargs = {'dates': data.get('dates'),
              'blues': data.get('blues'),
              'greens': data.get('greens'),
              'reds': data.get('reds'),
              'nirs': data.get('nirs'),
              'swir1s': data.get('swir1s'),
              'swir2s': data.get('swir2s'),
              'thermals': data.get('thermals'),
              'quality': data.get('quality'),
              'params': ccd_params()}

    return safely(func=ccd.detect, kwargs=kwargs, chip_x=chip_x, chip_y=chip_y,
                  x=x, y=y, alg=ccd.algorithm, datestr=acquired, errors=errs)


def fits_in_box(value, bbox):
    """Determines if a point value fits within a bounding box (edges inclusive)
    Useful as a filtering function with conditional enforcement.
    If bbox is None then fits_in_box always returns True

    Args:
        value (tuple): ((chip_x, chip_y, x, y), (data))
        bbox (dict): ulx, uly, lrx, lry

    Returns:
       bool
    """

    def fits(point, bbox):
        _, _, x, y = point
        return (float(x) >= float(bbox['ulx']) and
                float(x) <= float(bbox['lrx']) and
                float(y) >= float(bbox['lry']) and
                float(y) <= float(bbox['uly']))

    return bbox is None or fits(value[0], bbox)


def labels(inputs=None, ccd=None):
    """Associates friendly names to products

    Args:
        inputs (rdd): Inputs rdd
        ccd (rdd): CCD rdd

    Returns:
        dict: {label:rdd}
    """

    return {'inputs': inputs, 'ccd': ccd}


def timeseries(jobconf, spark_context):
    sc = spark_context
    acquired = jobconf['acquired'].value
    specs_fn = jobconf['specs_fn'].value
    chips_url = jobconf['chips_url'].value
    chips_fn = jobconf['chips_fn'].value
    clip_box = jobconf['clip_box'].value
    initial_partitions = jobconf['initial_partitions'].value
    product_partitions = jobconf['product_partitions'].value
    chip_ids = jobconf['chip_ids'].value

    _chipids = sc.parallelize(chip_ids, initial_partitions).setName("chip_ids")

    _in = _chipids.map(partial(merlin.create,
                               dates_fn=partial(
                                           f.chexists,
                                           check_fn=timeseries.symmetric_dates,
                                           keys=['quality']),
                               specs_fn=specs_fn,
                               chips_url=chips_url,
                               chips_fn=chips_fn,
                               acquired=acquired,
                               queries=queries))\
                               .flatMap(lambda x: x)\
                               .filter(partial(fits_in_box,
                                               bbox=clip_box))\
                               .map(lambda x: (success(chip_x=x[0][0],
                                                       chip_y=x[0][1],
                                                       x=x[0][2],
                                                       y=x[0][3],
                                                       alg=algorithm('timeseries'),
                                                       datestr=acquired,
                                                       result=x[1])))\
                               .repartition(product_partitions)\
                               .setName(algorithm('timeseries'))

    
def changedetection(timeseries):
    """Run change detection over a timeseries

    Args:
        timeseries (rdd): An RDD of timeseries 

    Returns:
        dict: rdd
    """

    return timeseries.map(pyccd).setName(ccd.algorithm).persist()


def train(product_graph, spark_context):
    # training_chipids()
    # requires ancillary data such as DEM, trends, et. al.
    #
    # TODO: This might require switching to the dataframe api and the
    # spark cassandra connector, especially if we are going to train on results
    # that already exist in cassandra.  Don't implement this without a
    # significant amount of hammock and whiteboard time.
    #
    # In order to send in appropriate chip ids to init, it will have
    # to accept chip ids instead of bounds and the bounds to chip id
    # determination will have to be done by whatever calls it.  This will
    # be necessary as training requires additional areas besides the area
    # one is actually attempting to train on.
    pass


def classify(product_graph, spark_context):
    # Same as the training graph.  This cannot run unless
    # #1 - There are ccd results and
    # #2 - The classifier has been trained.
    # Dont just jam these two things into this rdd graph setup.  Find the
    # cleanest way to represent and handle it.  It might require running
    # ccd first, training second and classification third.  Or they might all
    # be able to be put into the same graph and run at the same time.
    #
    # Regardless, all this data will need to be persisted so after its all
    # working we will probably need the ability to load data from iwds,
    # determine what else is needed (what areas are missing based on the
    # request) conditionally produce it, then proceed with the operations
    pass

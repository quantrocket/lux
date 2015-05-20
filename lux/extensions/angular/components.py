import json

from lux import Html
from lux.utils.crypt import get_random_string


def grid(options, id=None):
    if not id:
        id = 'grid_%s' % get_random_string(5)
    script = grid_script % (id, json.dumps(options))
    container = Html('div').attr('rest-grid', 'luxgrids.%s' % id)
    container.append(Html('div', cn='grid').attr('ui-grid', 'gridOptions'))
    container.append(script)
    return container.render()


grid_script = ('<script>if (!this.luxgrids) {this.luxgrids = {};} '
               'this.luxgrids.%s = %s;</script>')

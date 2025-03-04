""" Test script to compare coverage_results.xml with spec

Use pyucis to validate fir example coverage result generated
by FC4SC against specification.
"""

from io import BytesIO
from ucis.xml import validate_ucis_xml



def validate_ucis(file_name):
    """
    Validate UCIS function

    : arg file_name: The filename to validate
    : returns: status of validation. TODO:return
    """
    rc = False

    try:
      with open(file_name, encoding='utf-8') as f:
          xml_file = BytesIO(bytes(bytearray(f.read(), encoding='utf-8')))
          rc = validate_ucis_xml(xml_file)
    except:
        print("an exception occured")

    return rc 


def main() -> None:

    rc = validate_ucis('../../examples/fir/coverage_results.xml')
    return rc



if __name__ == '__main__':
  rc = main()
  if rc:
    print("validation OK")
  else:
    print("validation Failure")


from pathlib import Path
Path(__file__).with_name('IMPORT_MARKER.txt').write_text('harmless verifier marker\n')
def run(*a,**k):raise AssertionError('Unexpected worker execution')

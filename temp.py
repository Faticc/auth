import multiprocessing
import subprocess
import tempfile
import zipfile
import hashlib
import base64
import json
import glob
import sys
import os
from ..patcher.patcher import PatchRule, run_patcher

from typing import List, Dict
from auth.auth import PlayerProfile, ClientProfile, Params, Skin, Cloak, send_request

from pathlib import Path


# ==========================================
BJE_BASE64 = 'yv66vgAAADIBVwEAA2JqZQcAAQEAEGphdmEvbGFuZy9PYmplY3QHAAMBAApTb3VyY2VGaWxlAQAGPGluaXQ+AQANKExiYW87TGJqYjspVgEAAygpVgwABgAICgAEAAkBAAFjAQABSQwACwAMCQACAA0BAAFkDAAPAAwJAAIAEAEAAWUMABIADAkAAgATAQADYWhrBwAVAQABYgEABUxhaGs7DAAXABgJABYAGQEAAWsMABsAGAkAAgAcAQABYQEABUxiYW87DAAeAB8JAAIAIAEABUxiamI7DAAXACIJAAIAIwEAEShMYmFvO0xiamU7SUlJSSlWAQADYmFvBwAmAQABZgEABUxiamY7DAAoACkJACcAKgEAAWgBAAVMYmprOwwALAAtCQAnAC4BAANiamYHADABAAsoTHl6O0lJSUkpWgwAHgAyCgAxADMBAAcoSUlJSSlaDAAeADUKAAIANgEAByhMeXo7KVYBAAJ5egcAOQEAAmJFAQAETHl3OwwAOwA8CQA6AD0BAAcoTHl3OylWDAAeAD8KABYAQAEAAygpWgEACChMYWhrOylWAQADYmprBwBECQBFAD0EwzQAAAEAAXkBAAFGDABIAEkJADoASgwAEgBCCgAWAEwMAAsAQgoAFgBOAQAGKElJSSlaDAAPAFAKAEUAUQwADwBCCgAWAFMBAAJiZQEABygpTGFkZDsMAFUAVgoARQBXAQADYWRkBwBZAQAHKClMYWRiOwwAFwBbCgBaAFwBAANhZWgHAF4BAANhaGIHAGABAAooSUlJKUxhamk7DAAeAGIKAGEAYwEAA2FqaQcAZQEAAW8BAAcoKUxhd3Q7DABnAGgKAGYAaQEAA2F3dAcAawEABUxhd3Q7DAAeAG0JAGwAbgEACChMYWppOylJDAAXAHAKAGYAcQEABihJSUkpSQwAEgBzCgBhAHQBAAgoSUlJSUkpVgwACwB2CgBhAHcMACgAUAoAYQB5AQAMKExhaGI7SUlJSSlWDAAXAHsKAGYAfAEAAmJGDAB+AFYKAEUAfwEAFChMYWhiO0xhamk7SUlJTHl6OylWDAAeAIEKAFoAggwAFwAMCQBaAIQBAAJiRwwAhgAICgBFAIcBAAcoSUlJSSlWAQAEdGhpcwEAAmkxAQACaTIBAAJpMwEAAmk0AQACamkHAI8MAAYAdgoAkACRAQADYmpiBwCTAQAHKExmdDspVgwAHgCVCgCUAJYBAAVMYmplOwEAAWoBAAFaDACZAJoJAAIAmwEAAWcMAJ0ASQkAAgCeAQADKClJDABIAKAKAEUAoQwADwB2CgAxAKMMABcAiQoAAgClAQADKClGBECgAAAEQJAAAAwAGwAICgACAKoBAAYoKUxlajsMABcArAoAlACtAQACZWoHAK8KALAAUwwAHgAICgCwALIBAAYoKUxmajsMACgAtAoAsAC1AQAGKClMZmI7DAASALcKALAAuAEAAmZiBwC6AQAHKExmajspVgwAHgC8CwC7AL0BAAJmcQcAvwEAGERpc2Nvbm5lY3RlZCBmcm9tIHNlcnZlcggAwQEAFShMamF2YS9sYW5nL1N0cmluZzspVgwABgDDCgDAAMQBAAVMYWRkOwwAKADGCQACAMcBAA0oTGFkZDtMYWRkOylaDAAeAMkKAFoAygwAnQBCCgBaAMwMABsAoAoAWgDOAQACYm0BAARMeXg7DADQANEJAEUA0gEAAnl4BwDUCQDVAA0BAAFsDADXAAwJAAIA2AEAAmpsBwDaAQAEKEkpVgwABgDcCgDbAN0BABooTHl6O0xhaGI7TGFkZDtJSUlJTGF6dzspWgEAA2F6dwcA4AEAAUQMAB4A4gkA4QDjDAAXAOIJAOEA5QwACwDiCQDhAOcBAAJhbgwA6QBCCgA6AOoKADoAVwEAEyhMYWhiO0lJSUx5ejtJRkZGKVoMAB4A7QoAZgDuAQADYWJoBwDwAQAVKExhaGI7SUlJSUx5ejtMYWRkOylaDAAeAPIKAPEA8wEAAmpvBwD1CQA6ANIMACwAVgoA1QD4AQAPKElJSUlMYWRkO0ZGRilWDAAGAPoKAPYA+wEAEyhMeXo7TGFoYjtJSUlJRkZGKVoMAB4A/QoAWgD+DAAXANwKAFoBAAEAEShMeXo7TGFoYjtMYWRkOylaAQAQKExhaGI7THl6OylMYWRkOwwAHgEDCgBaAQQBAAZbTGFkZDsMAB4BBgkA1QEHAQAQKExhaGI7THBxOylMYmprOwEAAU0BAAcoKUxiYnM7DAEKAQsKACcBDAEAGyhMYmFvO0xhaGI7TGJicztMYmpiO0xwcTspVgwABgEOCgBFAQ8BAAsoTHl6O0xzYTspVgEAAmphBwESAQACamIHARQBAARMamI7DAAXARYJARUBFwEACyhMc2E7TGpiOylWDAAGARkKARMBGgEAAXIBAAcoTHNhOylWDAEcAR0KADoBHgEACyhMeXo7THNhOylaDAAeARYJARUBIQEAAXEBAAcoTHNhOylaDAEjASQKADoBJQEADyhJSUlJTHl6OylMYWRkOwEAAmJvAQAETHpzOwwBKAEpCQA6ASoBAAJ6cwcBLAEAByhMeXg7KVMMAB4BLgoBLQEvAQAOKElJSUx5ejspTGFkZDsMAB4BMQoBLQEyAQACaXgHATQBAA0oSUlJSUxhZGQ7UylWDAAGATYKATUBNwEABShJSSlWAQACaXcHAToMAAYBOQoBOwE8AQAJKExhZGQ7SSlWAQACam0HAT8BAAkoSUxhZGQ7KVYMAAYBQQoBQAFCAQAIKExhZGQ7KVYBAAJiQQwBRQAICgA6AUYBAAFpAQACYW0MAUkAQgoARQFKAQABbQEABExzYTsMAUwBTQkARQFOAQACd2kHAVABAARDb2RlAQAPTGluZU51bWJlclRhYmxlAQANU3RhY2tNYXBUYWJsZQEAEkxvY2FsVmFyaWFibGVUYWJsZQEAEE1ldGhvZFBhcmFtZXRlcnMAIQACAAQAAAAMABIAHgAfAAAAEgAXACIAAAACAAsADAAAAAIADwAMAAAAAgASAAwAAAACACgAxgAAAAIAnQBJAAAAAgAsAEkAAAACAUgADAAAAAIAmQCaAAAAAgAbABgAAAACANcADAAAAB4AAQAGAAcAAQFSAAAAWQACAAMAAAAlKrcACioCtQAOKgK1ABEqArUAFCqyABq1AB0qK7UAISostQAksQAAAAEBUwAAACIACAAAACEABAAXAAkAGAAOABkAEwAfABoAIgAfACMAJAAkAAkAHgAlAAEBUgAAAEkABgAGAAAAICq0ACsqtAAvHB0VBBUFtgA0mgAOKxwdFQQVBbYAN1exAAAAAgFUAAAAAwABHwFTAAAADgADAAAAJwAUACgAHwAqAAEAHgA4AAEBUgAAACgAAgACAAAADCq0AB0rtAA+tgBBsQAAAAEBUwAAAAoAAgAAAC0ACwAuAAEAHgBCAAEBUgAAABoAAQABAAAAAgOsAAAAAQFTAAAABgABAAAAMQABAB4AQwABAVIAAAA3AAIAAgAAABcqK7UAHSq0AB0qtAAhtAAvtABGtgBBsQAAAAEBUwAAAA4AAwAAADUABQA2ABYANwABABcAOAABAVIAAAAjAAIAAgAAAAcrEke1AEuxAAAAAQFTAAAACgACAAAAOgAGADsAAQAXAEIAAQFSAAAAIAABAAEAAAAIKrQAHbYATawAAAABAVMAAAAGAAEAAAA+AAEAHgA1AAEBUgAAAXgACgAKAAAA8Sq0AB22AE+ZABUqtAAhtAAvGxwdtgBSmgAFA6wqtAAdtgBUmQAlKrQAIbQAL7YAWMYAGCq0ACG0AC+2AFi2AF3BAF+ZAAUDrCq0ACG0ACs6BRkFGxwdtgBkOgYZBrYAarIAb6YABQOsGQURB9EbHB0ZBrgAchkFGxwdtgB1EAx4YLYAeBkFGxwdtgB1NgcZBRscHbYAejYIFQiZAA8ZBhkFGxwdFQe2AH0qArUAESq0AB22AFSaADkqtAAhtAAvtgCAOgkZCcYAKBkJGQUZBhscHSq0ACG0AC+2AIMZCbQAhZoADSq0ACG0AC+2AIgVCKwAAAACAVQAAAAVAAUcK/0AHwcAMQcAZv0AQAEB+wBEAVMAAABaABYAAABCAAoAQwAaAEQAHABIACYASQBGAEoASABOAFEATwBbAFIAaABUAIQAVgCOAFcAmABYAJ0AWQCpAFsArgBdALgAXgDEAF8AyQBgANwAYQDkAGIA7gBnAAEAFwCJAAIBUgAAAHkACAAFAAAAMyq0ACS7AJBZAxscHRUEtwCStgCXKrQAJLsAkFkFGxwdFQS3AJK2AJcqGxwdFQS2ADdXsQAAAAEBVQAAADQABQAAADMAigCYAAAAAAAzAIsADAABAAAAMwCMAAwAAgAAADMAjQAMAAMAAAAzAI4ADAAEAVYAAAAVBQCKAAAAiwAAAIwAAACNAAAAjgAAAAEACwAIAAEBUgAAAIQACAABAAAATyq0AJyZAB8qtAAkuwCQWQQqtAAOKrQAESq0ABQCtwCStgCXKgO1AJwqC7UAnyq0ACG0ACsqtAAhtAAvtgCiKrQADiq0ABEqtAAUArYApLEAAAACAVQAAAADAAEjAVMAAAAaAAYAAACQAAcAkQAjAJQAKACVAC0AlgBOAJcAAQALAIkAAgFSAAAAUAAFAAUAAAAKKhscHRUEtgCmsQAAAAEBVQAAADQABQAAAAoAigCYAAAAAAAKAIsADAABAAAACgCMAAwAAgAAAAoAjQAMAAMAAAAKAI4ADAAEAVYAAAAVBQCKAAAAiwAAAIwAAACNAAAAjgAAAAEADwCnAAEBUgAAADkAAQABAAAAECq0AB22AFSZAAYSqK4Sqa4AAAACAVQAAAADAAENAVMAAAAOAAMAAADIAAoAyQANAMsAAQASAAgAAQFSAAAAmwAEAAEAAABgKrcAqyq0ACS2AK62ALGZABAqtAAktgCutgCzpwBEKrQAJLYArrYAtsYAHyq0ACS2AK62ALkqtAAktgCutgC2uQC+AgCnABsqtAAktgCutgC5uwDAWRLCtwDFuQC+AgCxAAAAAgFUAAAABQADHigXAVMAAAAeAAcAAADPAAQA0wARANQAHgDVACsA1gBHANgAXwDaAAIAHgBQAAEBUgAAAMoAAgAGAAAAhyq0ACG0AC+2AFg6BCq0AMjHAAwZBMcABwSnAAQDNgUqtADIxgBBGQTGADwZBLYAXSq0AMi2AF2mACoZBCq0AMi4AMuZAB4ZBLYAzZoAEhkEtgDPKrQAyLYAz6AABwSnAAQDNgUbKrQADqAAHBwqtAARoAAUHSq0ABSgAAwVBZkABwSnAAQDrAAAAAIBVAAAABUACPwAHAcAWkAB/AA/AQNAAQEgQAEBUwAAABYABQAAAN8ADADgAB8A4QArAOIAZADkAAIAGwAIAAEBUgAAAGIABAACAAAALiq0ACG0AC+0ANO0ANY8Gyq0ANmfABoqG7UA2Sq0ACS7ANtZKrQA2bcA3rYAl7EAAAACAVQAAAAGAAH8AC0BAVMAAAAWAAUAAADoAA4A6QAWAOoAGwDrAC0A7QABAB4A3wABAVIAAAGgAAsAEAAAAQ0qtwCrGQi0AOSQFQSGZjgJGQi0AOaQFQWGZjgKGQi0AOiQFQaGZjgLAzYMK7YA65kACiu2AOzHACYsFQQVBRUGtgBkLBUEFQUVBisVBxcJFwoXC7YA75kABgQ2DBUMmgAvLcYAKy22AF3BAPGZACEttgBdwADxOg0ZDSwVBBUFFQYVBysttgD0mgAFA6wqtAAkuwD2WRUEFQUVBhUHK7QA97YA+RcJFwoXC7cA/LYAlxUMmQAFBKwtxwAFA6wqtAAdtgBUmQA0LbYAzzYNLbQAhTYOLSssFQQVBRUGFQcXCRcKFwu2AP82Dy0VDbYBAS0VDrUAhRUPrC0rLBUEFQUVBhUHFwkXChcLtgD/rAAAAAIBVAAAACUABv8AOQANBwACBwA6BwBhBwBaAQEBAQcA4QICAgEAACIwKQU6AVMAAABWABUAAADwAAQA8QAQAPIAHADzACgA9AArAPYAOQD3AFwA+gBvAPsAeAD8AI0A/wCwAQAAtwEBAL0BAwDHAQQAzQEFANMBBgDpAQcA7wEIAPUBCQD4AQsAAQAeAQIAAQFSAAAAvwALAAYAAAByKrcAqyq0ACS7APZZAgICEQD/K7QA97YA+QsLC7cA/LYAly20AIU2BC0sK7YBBToFGQUtpgASGQXGADgZBbQAhRUEnwAuK7QA97QBCCu0APe0ANYZBVMZBbQAhZoAEyu0APe0AQgrtAD3tADWAVMErAOsAAAAAgFUAAAACwAD/QBFAQcAWigBAVMAAAAqAAoAAAEQAAQBEQAiARIAKAETADABFQBFARYAVgEYAF4BGQBuARsAcAEeAAEAHgEJAAEBUgAAADEABwADAAAAGbsARVkqtAAhKyq0ACG2AQ0qtAAkLLcBELAAAAABAVMAAAAGAAEAAAEiAAEAHgERAAEBUgAAAEAABQADAAAAHCq3AKsqtAAkuwETWSyyARi3ARu2AJcrLLYBH7EAAAABAVMAAAASAAQAAAEmAAQBJwAWASgAGwEpAAEAFwEgAAEBUgAAADwABQADAAAAHCq3AKsqtAAkuwETWSyyASK3ARu2AJcrLLYBJqwAAAABAVMAAAAOAAMAAAEsAAQBLQAWAS4AAQAeAScAAQFSAAAAXQAJAAgAAAA5GQW0ASsZBbQA97YBMDYGGQW0ASscHRUEGQW2ATM6Byq0ACS7ATVZGxwdFQQZBxUGtwE4tgCXGQewAAAAAQFTAAAAEgAEAAABMgAPATQAHwE1ADYBNwABAB4BOQABAVIAAAAtAAUAAwAAABEqtAAkuwE7WRsctwE9tgCXsQAAAAEBUwAAAAoAAgAAATsAEAE8AAEAHgE+AAEBUgAAAEQABQADAAAAGyq0AB22AFSZABMqtAAkuwFAWRwrtwFDtgCXsQAAAAIBVAAAAAMAARoBUwAAAA4AAwAAAT8ACgFAABoBQgABAB4BRAABAVIAAABIAAUAAgAAAB8qtAAdtgBUmQAXK8YAEyq0ACS7AUBZAiu3AUO2AJexAAAAAgFUAAAAAwABHgFTAAAADgADAAABRQAOAUYAHgFIAAEACwA4AAEBUgAAAEIACAACAAAAHiq3AKsqtAAkuwCQWQgDAwMRAP+3AJK2AJcrtgFHsQAAAAEBUwAAABIABAAAAUsABAFMABkBTQAdAU4AAQAoAEIAAQFSAAAAIAABAAEAAAAIKrQAHbYATawAAAABAVMAAAAGAAEAAAFRAAEAnQBCAAEBUgAAADMAAQABAAAAECq0AB22AFSaAAcEpwAEA6wAAAACAVQAAAAFAAIOQAEBUwAAAAYAAQAAAVUAAQAsAEIAAQFSAAAAIAABAAEAAAAIKrQAHbYAVKwAAAABAVMAAAAGAAEAAAFZAAEBSABCAAEBUgAAACAAAQABAAAACCq0AB22AFSsAAAAAQFTAAAABgABAAABXQABAJkAQgABAVIAAABGAAEAAQAAACMqtAAhtAAvtgFLmQAXKrQAIbQAL7QBT8EBUZkABwSnAAQDrAAAAAIBVAAAAAUAAiFAAQFTAAAABgABAAABZwABAAUAAAACAAU='
REFMAP_JSON_BASE64 = 'ewogICJtYXBwaW5ncyI6IHsKICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L2NsaWVudC92YW5pbGxhL01peGluQzAwUGFja2V0TG9naW5TdGFydCI6IHsKICAgICAgIndyaXRlUGFja2V0RGF0YSI6ICJMbmV0L21pbmVjcmFmdC9uZXR3b3JrL2xvZ2luL2NsaWVudC9DMDBQYWNrZXRMb2dpblN0YXJ0O2Z1bmNfMTQ4ODQwX2IoTG5ldC9taW5lY3JhZnQvbmV0d29yay9QYWNrZXRCdWZmZXI7KVYiCiAgICB9LAogICAgInJ1L3NreV9kcml2ZS9taXhpbnMvZWFybHkvY2xpZW50L3ZhbmlsbGEvTWl4aW5HdWlDb250YWluZXJDcmVhdGl2ZSI6IHsKICAgICAgIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9lbnRpdHkvUmVuZGVySXRlbTtyZW5kZXJJdGVtQW5kRWZmZWN0SW50b0dVSShMbmV0L21pbmVjcmFmdC9jbGllbnQvZ3VpL0ZvbnRSZW5kZXJlcjtMbmV0L21pbmVjcmFmdC9jbGllbnQvcmVuZGVyZXIvdGV4dHVyZS9UZXh0dXJlTWFuYWdlcjtMbmV0L21pbmVjcmFmdC9pdGVtL0l0ZW1TdGFjaztJSSlWIjogIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9lbnRpdHkvUmVuZGVySXRlbTtmdW5jXzgyNDA2X2IoTG5ldC9taW5lY3JhZnQvY2xpZW50L2d1aS9Gb250UmVuZGVyZXI7TG5ldC9taW5lY3JhZnQvY2xpZW50L3JlbmRlcmVyL3RleHR1cmUvVGV4dHVyZU1hbmFnZXI7TG5ldC9taW5lY3JhZnQvaXRlbS9JdGVtU3RhY2s7SUkpViIsCiAgICAgICJmdW5jXzE0NzA1MV9hIjogIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9ndWkvaW52ZW50b3J5L0d1aUNvbnRhaW5lckNyZWF0aXZlO2Z1bmNfMTQ3MDUxX2EoTG5ldC9taW5lY3JhZnQvY3JlYXRpdmV0YWIvQ3JlYXRpdmVUYWJzOylWIgogICAgfSwKICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L2NsaWVudC92YW5pbGxhL01peGluSXRlbVJlbmRlcmVyIjogewogICAgICAicmVuZGVySW5zaWRlT2ZCbG9jayI6ICJMbmV0L21pbmVjcmFmdC9jbGllbnQvcmVuZGVyZXIvSXRlbVJlbmRlcmVyO2Z1bmNfNzg0NDZfYShGTG5ldC9taW5lY3JhZnQvdXRpbC9JSWNvbjspViIKICAgIH0sCiAgICAicnUvc2t5X2RyaXZlL21peGlucy9lYXJseS9jbGllbnQvdmFuaWxsYS9NaXhpblJlbmRlckJsb2NrcyI6IHsKICAgICAgIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9SZW5kZXJCbG9ja3M7c2V0UmVuZGVyQm91bmRzRnJvbUJsb2NrKExuZXQvbWluZWNyYWZ0L2Jsb2NrL0Jsb2NrOylWIjogIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9SZW5kZXJCbG9ja3M7ZnVuY18xNDc3NzVfYShMbmV0L21pbmVjcmFmdC9ibG9jay9CbG9jazspViIsCiAgICAgICJyZW5kZXJCbG9ja0FzSXRlbSI6ICJMbmV0L21pbmVjcmFmdC9jbGllbnQvcmVuZGVyZXIvUmVuZGVyQmxvY2tzO2Z1bmNfMTQ3ODAwX2EoTG5ldC9taW5lY3JhZnQvYmxvY2svQmxvY2s7SUYpViIKICAgIH0sCiAgICAicnUvc2t5X2RyaXZlL21peGlucy9lYXJseS9jbGllbnQvdmFuaWxsYS9NaXhpblJlbmRlckdsb2JhbCI6IHsKICAgICAgImRyYXdPdXRsaW5lZEJvdW5kaW5nQm94IjogIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9SZW5kZXJHbG9iYWw7ZnVuY18xNDc1OTBfYShMbmV0L21pbmVjcmFmdC91dGlsL0F4aXNBbGlnbmVkQkI7SSlWIiwKICAgICAgIm1hcmtCbG9ja3NGb3JVcGRhdGUiOiAiTG5ldC9taW5lY3JhZnQvY2xpZW50L3JlbmRlcmVyL1JlbmRlckdsb2JhbDtmdW5jXzcyNzI1X2IoSUlJSUlJKVYiCiAgICB9LAogICAgInJ1L3NreV9kcml2ZS9taXhpbnMvZWFybHkvc2VydmVyL3ZhbmlsbGEvTWl4aW5BbnZpbENodW5rTG9hZGVyIjogewogICAgICAic2F2ZUNodW5rIjogIkxuZXQvbWluZWNyYWZ0L3dvcmxkL2NodW5rL3N0b3JhZ2UvQW52aWxDaHVua0xvYWRlcjtmdW5jXzc1ODE2X2EoTG5ldC9taW5lY3JhZnQvd29ybGQvV29ybGQ7TG5ldC9taW5lY3JhZnQvd29ybGQvY2h1bmsvQ2h1bms7KVYiCiAgICB9LAogICAgInJ1L3NreV9kcml2ZS9taXhpbnMvZWFybHkvc2VydmVyL3ZhbmlsbGEvTWl4aW5DMDBQYWNrZXRMb2dpblN0YXJ0IjogewogICAgICAicmVhZFBhY2tldERhdGEiOiAiTG5ldC9taW5lY3JhZnQvbmV0d29yay9sb2dpbi9jbGllbnQvQzAwUGFja2V0TG9naW5TdGFydDtmdW5jXzE0ODgzN19hKExuZXQvbWluZWNyYWZ0L25ldHdvcmsvUGFja2V0QnVmZmVyOylWIgogICAgfSwKICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L3NlcnZlci92YW5pbGxhL01peGluQ29udGFpbmVyRW5jaGFudG1lbnQiOiB7CiAgICAgICJlbmNoYW50SXRlbSI6ICJMbmV0L21pbmVjcmFmdC9pbnZlbnRvcnkvQ29udGFpbmVyRW5jaGFudG1lbnQ7ZnVuY183NTE0MF9hKExuZXQvbWluZWNyYWZ0L2VudGl0eS9wbGF5ZXIvRW50aXR5UGxheWVyO0kpWiIKICAgIH0sCiAgICAicnUvc2t5X2RyaXZlL21peGlucy9lYXJseS9zZXJ2ZXIvdmFuaWxsYS9NaXhpbkVudGl0eUxpdmluZ0Jhc2UiOiB7CiAgICAgICJMbmV0L21pbmVjcmFmdC9lbnRpdHkvRW50aXR5TGl2aW5nQmFzZTthdHRhY2tFbnRpdHlGcm9tKExuZXQvbWluZWNyYWZ0L3V0aWwvRGFtYWdlU291cmNlO0YpWiI6ICJMbmV0L21pbmVjcmFmdC9lbnRpdHkvRW50aXR5TGl2aW5nQmFzZTtmdW5jXzcwMDk3X2EoTG5ldC9taW5lY3JhZnQvdXRpbC9EYW1hZ2VTb3VyY2U7RilaIiwKICAgICAgIm9uRW50aXR5VXBkYXRlIjogIkxuZXQvbWluZWNyYWZ0L2VudGl0eS9FbnRpdHlMaXZpbmdCYXNlO2Z1bmNfNzAwMzBfeigpViIKICAgIH0sCiAgICAicnUvc2t5X2RyaXZlL21peGlucy9lYXJseS9zZXJ2ZXIvdmFuaWxsYS9NaXhpbkl0ZW1Ta3VsbCI6IHsKICAgICAgIm9uSXRlbVVzZSI6ICJMbmV0L21pbmVjcmFmdC9pdGVtL0l0ZW1Ta3VsbDtmdW5jXzc3NjQ4X2EoTG5ldC9taW5lY3JhZnQvaXRlbS9JdGVtU3RhY2s7TG5ldC9taW5lY3JhZnQvZW50aXR5L3BsYXllci9FbnRpdHlQbGF5ZXI7TG5ldC9taW5lY3JhZnQvd29ybGQvV29ybGQ7SUlJSUZGRilaIgogICAgfSwKICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L3NlcnZlci92YW5pbGxhL01peGluTmV0SGFuZGxlckxvZ2luU2VydmVyIjogewogICAgICAiTG5ldC9taW5lY3JhZnQvc2VydmVyL25ldHdvcmsvTmV0SGFuZGxlckxvZ2luU2VydmVyO2Z1bmNfMTQ3MzI2X2MoKVYiOiAiTG5ldC9taW5lY3JhZnQvc2VydmVyL25ldHdvcmsvTmV0SGFuZGxlckxvZ2luU2VydmVyO2Z1bmNfMTQ3MzI2X2MoKVYiLAogICAgICAib25OZXR3b3JrVGljayI6ICJMbmV0L21pbmVjcmFmdC9zZXJ2ZXIvbmV0d29yay9OZXRIYW5kbGVyTG9naW5TZXJ2ZXI7ZnVuY18xNDcyMzNfYSgpViIsCiAgICAgICJwcm9jZXNzTG9naW5TdGFydCI6ICJMbmV0L21pbmVjcmFmdC9zZXJ2ZXIvbmV0d29yay9OZXRIYW5kbGVyTG9naW5TZXJ2ZXI7ZnVuY18xNDczMTZfYShMbmV0L21pbmVjcmFmdC9uZXR3b3JrL2xvZ2luL2NsaWVudC9DMDBQYWNrZXRMb2dpblN0YXJ0OylWIgogICAgfSwKICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L3NlcnZlci92YW5pbGxhL01peGluTmV0SGFuZGxlclBsYXlTZXJ2ZXIiOiB7CiAgICAgICJoYW5kbGVTbGFzaENvbW1hbmQiOiAiTG5ldC9taW5lY3JhZnQvbmV0d29yay9OZXRIYW5kbGVyUGxheVNlcnZlcjtmdW5jXzE0NzM2MV9kKExqYXZhL2xhbmcvU3RyaW5nOylWIgogICAgfSwKICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L3NlcnZlci92YW5pbGxhL01peGluV2l0aGVyIjogewogICAgICAiTG5ldC9taW5lY3JhZnQvd29ybGQvV29ybGQ7bmV3RXhwbG9zaW9uKExuZXQvbWluZWNyYWZ0L2VudGl0eS9FbnRpdHk7RERERlpaKUxuZXQvbWluZWNyYWZ0L3dvcmxkL0V4cGxvc2lvbjsiOiAiTG5ldC9taW5lY3JhZnQvd29ybGQvV29ybGQ7ZnVuY183Mjg4NV9hKExuZXQvbWluZWNyYWZ0L2VudGl0eS9FbnRpdHk7RERERlpaKUxuZXQvbWluZWNyYWZ0L3dvcmxkL0V4cGxvc2lvbjsiLAogICAgICAidXBkYXRlQUlUYXNrcyI6ICJMbmV0L21pbmVjcmFmdC9lbnRpdHkvYm9zcy9FbnRpdHlXaXRoZXI7ZnVuY183MDYxOV9iYygpViIKICAgIH0sCiAgICAicnUvc2t5X2RyaXZlL21peGlucy9sYXRlL3NlcnZlci9kcmFjb25pYy9NaXhpbk1pbmVjcmFmdEZvcmdlRXZlbnRIYW5kbGVyIjogewogICAgICAiTG5ldC9taW5lY3JhZnQvd29ybGQvV29ybGQ7c3Bhd25FbnRpdHlJbldvcmxkKExuZXQvbWluZWNyYWZ0L2VudGl0eS9FbnRpdHk7KVoiOiAiTG5ldC9taW5lY3JhZnQvd29ybGQvV29ybGQ7ZnVuY183MjgzOF9kKExuZXQvbWluZWNyYWZ0L2VudGl0eS9FbnRpdHk7KVoiCiAgICB9LAogICAgInJ1L3NreV9kcml2ZS9taXhpbnMvbGF0ZS9zZXJ2ZXIvZXRmdXR1cnVtL01peGluQ29udGFpbmVyRW5jaGFudG1lbnQiOiB7CiAgICAgICJlbmNoYW50SXRlbSI6ICJMZ2FueW1lZGVzMDEvZXRmdXR1cnVtL2ludmVudG9yeS9Db250YWluZXJFbmNoYW50bWVudDtmdW5jXzc1MTQwX2EoTG5ldC9taW5lY3JhZnQvZW50aXR5L3BsYXllci9FbnRpdHlQbGF5ZXI7SSlaIgogICAgfQogIH0sCiAgImRhdGEiOiB7CiAgICAic2VhcmdlIjogewogICAgICAicnUvc2t5X2RyaXZlL21peGlucy9lYXJseS9jbGllbnQvdmFuaWxsYS9NaXhpbkMwMFBhY2tldExvZ2luU3RhcnQiOiB7CiAgICAgICAgIndyaXRlUGFja2V0RGF0YSI6ICJMbmV0L21pbmVjcmFmdC9uZXR3b3JrL2xvZ2luL2NsaWVudC9DMDBQYWNrZXRMb2dpblN0YXJ0O2Z1bmNfMTQ4ODQwX2IoTG5ldC9taW5lY3JhZnQvbmV0d29yay9QYWNrZXRCdWZmZXI7KVYiCiAgICAgIH0sCiAgICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L2NsaWVudC92YW5pbGxhL01peGluR3VpQ29udGFpbmVyQ3JlYXRpdmUiOiB7CiAgICAgICAgIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9lbnRpdHkvUmVuZGVySXRlbTtyZW5kZXJJdGVtQW5kRWZmZWN0SW50b0dVSShMbmV0L21pbmVjcmFmdC9jbGllbnQvZ3VpL0ZvbnRSZW5kZXJlcjtMbmV0L21pbmVjcmFmdC9jbGllbnQvcmVuZGVyZXIvdGV4dHVyZS9UZXh0dXJlTWFuYWdlcjtMbmV0L21pbmVjcmFmdC9pdGVtL0l0ZW1TdGFjaztJSSlWIjogIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9lbnRpdHkvUmVuZGVySXRlbTtmdW5jXzgyNDA2X2IoTG5ldC9taW5lY3JhZnQvY2xpZW50L2d1aS9Gb250UmVuZGVyZXI7TG5ldC9taW5lY3JhZnQvY2xpZW50L3JlbmRlcmVyL3RleHR1cmUvVGV4dHVyZU1hbmFnZXI7TG5ldC9taW5lY3JhZnQvaXRlbS9JdGVtU3RhY2s7SUkpViIsCiAgICAgICAgImZ1bmNfMTQ3MDUxX2EiOiAiTG5ldC9taW5lY3JhZnQvY2xpZW50L2d1aS9pbnZlbnRvcnkvR3VpQ29udGFpbmVyQ3JlYXRpdmU7ZnVuY18xNDcwNTFfYShMbmV0L21pbmVjcmFmdC9jcmVhdGl2ZXRhYi9DcmVhdGl2ZVRhYnM7KVYiCiAgICAgIH0sCiAgICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L2NsaWVudC92YW5pbGxhL01peGluSXRlbVJlbmRlcmVyIjogewogICAgICAgICJyZW5kZXJJbnNpZGVPZkJsb2NrIjogIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9JdGVtUmVuZGVyZXI7ZnVuY183ODQ0Nl9hKEZMbmV0L21pbmVjcmFmdC91dGlsL0lJY29uOylWIgogICAgICB9LAogICAgICAicnUvc2t5X2RyaXZlL21peGlucy9lYXJseS9jbGllbnQvdmFuaWxsYS9NaXhpblBsYXllckNvbnRyb2xsZXJNUCI6IHsKICAgICAgICAib25QbGF5ZXJEYW1hZ2VCbG9jayI6ICJMbmV0L21pbmVjcmFmdC9jbGllbnQvbXVsdGlwbGF5ZXIvUGxheWVyQ29udHJvbGxlck1QO2Z1bmNfNzg3NTlfYyhJSUlJKVYiCiAgICAgIH0sCiAgICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L2NsaWVudC92YW5pbGxhL01peGluUmVuZGVyQmxvY2tzIjogewogICAgICAgICJMbmV0L21pbmVjcmFmdC9jbGllbnQvcmVuZGVyZXIvUmVuZGVyQmxvY2tzO3NldFJlbmRlckJvdW5kc0Zyb21CbG9jayhMbmV0L21pbmVjcmFmdC9ibG9jay9CbG9jazspViI6ICJMbmV0L21pbmVjcmFmdC9jbGllbnQvcmVuZGVyZXIvUmVuZGVyQmxvY2tzO2Z1bmNfMTQ3Nzc1X2EoTG5ldC9taW5lY3JhZnQvYmxvY2svQmxvY2s7KVYiLAogICAgICAgICJyZW5kZXJCbG9ja0FzSXRlbSI6ICJMbmV0L21pbmVjcmFmdC9jbGllbnQvcmVuZGVyZXIvUmVuZGVyQmxvY2tzO2Z1bmNfMTQ3ODAwX2EoTG5ldC9taW5lY3JhZnQvYmxvY2svQmxvY2s7SUYpViIKICAgICAgfSwKICAgICAgInJ1L3NreV9kcml2ZS9taXhpbnMvZWFybHkvY2xpZW50L3ZhbmlsbGEvTWl4aW5SZW5kZXJHbG9iYWwiOiB7CiAgICAgICAgImRyYXdPdXRsaW5lZEJvdW5kaW5nQm94IjogIkxuZXQvbWluZWNyYWZ0L2NsaWVudC9yZW5kZXJlci9SZW5kZXJHbG9iYWw7ZnVuY18xNDc1OTBfYShMbmV0L21pbmVjcmFmdC91dGlsL0F4aXNBbGlnbmVkQkI7SSlWIiwKICAgICAgICAibWFya0Jsb2Nrc0ZvclVwZGF0ZSI6ICJMbmV0L21pbmVjcmFmdC9jbGllbnQvcmVuZGVyZXIvUmVuZGVyR2xvYmFsO2Z1bmNfNzI3MjVfYihJSUlJSUkpViIKICAgICAgfSwKICAgICAgInJ1L3NreV9kcml2ZS9taXhpbnMvZWFybHkvc2VydmVyL3ZhbmlsbGEvTWl4aW5BbnZpbENodW5rTG9hZGVyIjogewogICAgICAgICJzYXZlQ2h1bmsiOiAiTG5ldC9taW5lY3JhZnQvd29ybGQvY2h1bmsvc3RvcmFnZS9BbnZpbENodW5rTG9hZGVyO2Z1bmNfNzU4MTZfYShMbmV0L21pbmVjcmFmdC93b3JsZC9Xb3JsZDtMbmV0L21pbmVjcmFmdC93b3JsZC9jaHVuay9DaHVuazspViIKICAgICAgfSwKICAgICAgInJ1L3NreV9kcml2ZS9taXhpbnMvZWFybHkvc2VydmVyL3ZhbmlsbGEvTWl4aW5DMDBQYWNrZXRMb2dpblN0YXJ0IjogewogICAgICAgICJyZWFkUGFja2V0RGF0YSI6ICJMbmV0L21pbmVjcmFmdC9uZXR3b3JrL2xvZ2luL2NsaWVudC9DMDBQYWNrZXRMb2dpblN0YXJ0O2Z1bmNfMTQ4ODM3X2EoTG5ldC9taW5lY3JhZnQvbmV0d29yay9QYWNrZXRCdWZmZXI7KVYiCiAgICAgIH0sCiAgICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L3NlcnZlci92YW5pbGxhL01peGluQ29udGFpbmVyRW5jaGFudG1lbnQiOiB7CiAgICAgICAgImVuY2hhbnRJdGVtIjogIkxuZXQvbWluZWNyYWZ0L2ludmVudG9yeS9Db250YWluZXJFbmNoYW50bWVudDtmdW5jXzc1MTQwX2EoTG5ldC9taW5lY3JhZnQvZW50aXR5L3BsYXllci9FbnRpdHlQbGF5ZXI7SSlaIgogICAgICB9LAogICAgICAicnUvc2t5X2RyaXZlL21peGlucy9lYXJseS9zZXJ2ZXIvdmFuaWxsYS9NaXhpbkVudGl0eUxpdmluZ0Jhc2UiOiB7CiAgICAgICAgIkxuZXQvbWluZWNyYWZ0L2VudGl0eS9FbnRpdHlMaXZpbmdCYXNlO2F0dGFja0VudGl0eUZyb20oTG5ldC9taW5lY3JhZnQvdXRpbC9EYW1hZ2VTb3VyY2U7RilaIjogIkxuZXQvbWluZWNyYWZ0L2VudGl0eS9FbnRpdHlMaXZpbmdCYXNlO2Z1bmNfNzAwOTdfYShMbmV0L21pbmVjcmFmdC91dGlsL0RhbWFnZVNvdXJjZTtGKVoiLAogICAgICAgICJvbkVudGl0eVVwZGF0ZSI6ICJMbmV0L21pbmVjcmFmdC9lbnRpdHkvRW50aXR5TGl2aW5nQmFzZTtmdW5jXzcwMDMwX3ooKVYiCiAgICAgIH0sCiAgICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L3NlcnZlci92YW5pbGxhL01peGluSXRlbVNrdWxsIjogewogICAgICAgICJvbkl0ZW1Vc2UiOiAiTG5ldC9taW5lY3JhZnQvaXRlbS9JdGVtU2t1bGw7ZnVuY183NzY0OF9hKExuZXQvbWluZWNyYWZ0L2l0ZW0vSXRlbVN0YWNrO0xuZXQvbWluZWNyYWZ0L2VudGl0eS9wbGF5ZXIvRW50aXR5UGxheWVyO0xuZXQvbWluZWNyYWZ0L3dvcmxkL1dvcmxkO0lJSUlGRkYpWiIKICAgICAgfSwKICAgICAgInJ1L3NreV9kcml2ZS9taXhpbnMvZWFybHkvc2VydmVyL3ZhbmlsbGEvTWl4aW5OZXRIYW5kbGVyTG9naW5TZXJ2ZXIiOiB7CiAgICAgICAgIkxuZXQvbWluZWNyYWZ0L3NlcnZlci9uZXR3b3JrL05ldEhhbmRsZXJMb2dpblNlcnZlcjtmdW5jXzE0NzMyNl9jKClWIjogIkxuZXQvbWluZWNyYWZ0L3NlcnZlci9uZXR3b3JrL05ldEhhbmRsZXJMb2dpblNlcnZlcjtmdW5jXzE0NzMyNl9jKClWIiwKICAgICAgICAib25OZXR3b3JrVGljayI6ICJMbmV0L21pbmVjcmFmdC9zZXJ2ZXIvbmV0d29yay9OZXRIYW5kbGVyTG9naW5TZXJ2ZXI7ZnVuY18xNDcyMzNfYSgpViIsCiAgICAgICAgInByb2Nlc3NMb2dpblN0YXJ0IjogIkxuZXQvbWluZWNyYWZ0L3NlcnZlci9uZXR3b3JrL05ldEhhbmRsZXJMb2dpblNlcnZlcjtmdW5jXzE0NzMxNl9hKExuZXQvbWluZWNyYWZ0L25ldHdvcmsvbG9naW4vY2xpZW50L0MwMFBhY2tldExvZ2luU3RhcnQ7KVYiCiAgICAgIH0sCiAgICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L3NlcnZlci92YW5pbGxhL01peGluTmV0SGFuZGxlclBsYXlTZXJ2ZXIiOiB7CiAgICAgICAgImhhbmRsZVNsYXNoQ29tbWFuZCI6ICJMbmV0L21pbmVjcmFmdC9uZXR3b3JrL05ldEhhbmRsZXJQbGF5U2VydmVyO2Z1bmNfMTQ3MzYxX2QoTGphdmEvbGFuZy9TdHJpbmc7KVYiCiAgICAgIH0sCiAgICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2Vhcmx5L3NlcnZlci92YW5pbGxhL01peGluV2l0aGVyIjogewogICAgICAgICJMbmV0L21pbmVjcmFmdC93b3JsZC9Xb3JsZDtuZXdFeHBsb3Npb24oTG5ldC9taW5lY3JhZnQvZW50aXR5L0VudGl0eTtERERGWlopTG5ldC9taW5lY3JhZnQvd29ybGQvRXhwbG9zaW9uOyI6ICJMbmV0L21pbmVjcmFmdC93b3JsZC9Xb3JsZDtmdW5jXzcyODg1X2EoTG5ldC9taW5lY3JhZnQvZW50aXR5L0VudGl0eTtERERGWlopTG5ldC9taW5lY3JhZnQvd29ybGQvRXhwbG9zaW9uOyIsCiAgICAgICAgInVwZGF0ZUFJVGFza3MiOiAiTG5ldC9taW5lY3JhZnQvZW50aXR5L2Jvc3MvRW50aXR5V2l0aGVyO2Z1bmNfNzA2MTlfYmMoKVYiCiAgICAgIH0sCiAgICAgICJydS9za3lfZHJpdmUvbWl4aW5zL2xhdGUvc2VydmVyL2RyYWNvbmljL01peGluTWluZWNyYWZ0Rm9yZ2VFdmVudEhhbmRsZXIiOiB7CiAgICAgICAgIkxuZXQvbWluZWNyYWZ0L3dvcmxkL1dvcmxkO3NwYXduRW50aXR5SW5Xb3JsZChMbmV0L21pbmVjcmFmdC9lbnRpdHkvRW50aXR5OylaIjogIkxuZXQvbWluZWNyYWZ0L3dvcmxkL1dvcmxkO2Z1bmNfNzI4MzhfZChMbmV0L21pbmVjcmFmdC9lbnRpdHkvRW50aXR5OylaIgogICAgICB9LAogICAgICAicnUvc2t5X2RyaXZlL21peGlucy9sYXRlL3NlcnZlci9ldGZ1dHVydW0vTWl4aW5Db250YWluZXJFbmNoYW50bWVudCI6IHsKICAgICAgICAiZW5jaGFudEl0ZW0iOiAiTGdhbnltZWRlczAxL2V0ZnV0dXJ1bS9pbnZlbnRvcnkvQ29udGFpbmVyRW5jaGFudG1lbnQ7ZnVuY183NTE0MF9hKExuZXQvbWluZWNyYWZ0L2VudGl0eS9wbGF5ZXIvRW50aXR5UGxheWVyO0kpWiIKICAgICAgfQogICAgfQogIH0KfQ=='
EARLY_JSON_BASE64 = 'ewogICJyZXF1aXJlZCI6IHRydWUsCiAgInRhcmdldCI6ICJAZW52KERFRkFVTFQpIiwKICAibWluVmVyc2lvbiI6ICIwLjguNS1HVE5IIiwKICAiY29tcGF0aWJpbGl0eUxldmVsIjogIkpBVkFfOCIsCiAgInBhY2thZ2UiOiAicnUuc2t5X2RyaXZlLm1peGlucy5lYXJseSIsCiAgInJlZm1hcCI6ICJtaXhpbnMuZHdjaXR5LnJlZm1hcC5qc29uIiwKICAicGx1Z2luIjogInJ1LnNreV9kcml2ZS5taXhpbnMuTWl4aW5Db25maWdQbHVnaW4iLAogICJtaXhpbnMiOiBbCiAgICAiY29tbW9uLnZhbmlsbGEuTWl4aW5CbG9ja0ZlbmNlIiwKICAgICJjb21tb24udmFuaWxsYS5NaXhpbkJsb2NrVmluZSIKICBdLAogICJjbGllbnQiOiBbCiAgICAiY2xpZW50LnZhbmlsbGEuTWl4aW5DMDBQYWNrZXRMb2dpblN0YXJ0IiwKICAgICJjbGllbnQudmFuaWxsYS5NaXhpbkd1aUNvbnRhaW5lckNyZWF0aXZlIiwKICAgICJjbGllbnQudmFuaWxsYS5NaXhpbkd1aVNjcmVlbiIsCiAgICAiY2xpZW50LnZhbmlsbGEuTWl4aW5JdGVtUmVuZGVyZXIiLAogICAgImNsaWVudC52YW5pbGxhLk1peGluTWluZWNyYWZ0IiwKICAgICJjbGllbnQudmFuaWxsYS5NaXhpblJlbmRlckJsb2NrcyIsCiAgICAiY2xpZW50LnZhbmlsbGEuTWl4aW5SZW5kZXJHbG9iYWwiCiAgXSwKICAic2VydmVyIjogWwogICAgInNlcnZlci52YW5pbGxhLkZNTE5ldHdvcmtIYW5kbGVyTWl4aW4iLAogICAgInNlcnZlci52YW5pbGxhLk1peGluQW52aWxDaHVua0xvYWRlciIsCiAgICAic2VydmVyLnZhbmlsbGEuTWl4aW5DMDBQYWNrZXRMb2dpblN0YXJ0IiwKICAgICJzZXJ2ZXIudmFuaWxsYS5NaXhpbkNvbnRhaW5lckVuY2hhbnRtZW50IiwKICAgICJzZXJ2ZXIudmFuaWxsYS5NaXhpbkVudGl0eUxpdmluZ0Jhc2UiLAogICAgInNlcnZlci52YW5pbGxhLk1peGluRW50aXR5UGxheWVyTVAiLAogICAgInNlcnZlci52YW5pbGxhLk1peGluSXRlbVNrdWxsIiwKICAgICJzZXJ2ZXIudmFuaWxsYS5NaXhpbk5ldEhhbmRsZXJMb2dpblNlcnZlciIsCiAgICAic2VydmVyLnZhbmlsbGEuTWl4aW5OZXRIYW5kbGVyUGxheVNlcnZlciIsCiAgICAic2VydmVyLnZhbmlsbGEuTWl4aW5XaXRoZXIiCiAgXQp9'
# ==========================================

rules = [
    PatchRule(
        name="PathMineSpeed",
        search_mask="mods/DwCity*.jar",
        delete_files=[],
        replace_files={
            "mixins.dwcity.refmap.json": REFMAP_JSON_BASE64,
            "mixins.dwcity.early.json": EARLY_JSON_BASE64
        },
        add_files={}
    ),
    PatchRule(
        name="PathMineSpeed",
        search_mask="minecraft.jar",
        delete_files=[],
        replace_files={
            "bje.class": BJE_BASE64
        },
        add_files={}
    ),
]


# лаунчер
JVM_ARGS = [
    '-XX:HeapDumpPath=ThisTricksIntelDriversForPerformance_javaw.exe_minecraft.exe.heapdump',
    '-Djava.system.class.loader=com.gtnewhorizons.retrofuturabootstrap.RfbSystemClassLoader',
    '--enable-native-access', 'ALL-UNNAMED',
    '--add-opens', 'java.base/java.io=ALL-UNNAMED',
    '--add-opens', 'java.base/java.lang.invoke=ALL-UNNAMED',
    '--add-opens', 'java.base/java.lang.ref=ALL-UNNAMED',
    '--add-opens', 'java.base/java.lang.reflect=ALL-UNNAMED',
    '--add-opens', 'java.base/java.lang=ALL-UNNAMED',
    '--add-opens', 'java.base/java.net.spi=ALL-UNNAMED',
    '--add-opens', 'java.base/java.net=ALL-UNNAMED',
    '--add-opens', 'java.base/java.nio.channels=ALL-UNNAMED',
    '--add-opens', 'java.base/java.nio.charset=ALL-UNNAMED',
    '--add-opens', 'java.base/java.nio.file=ALL-UNNAMED',
    '--add-opens', 'java.base/java.nio=ALL-UNNAMED',
    '--add-opens', 'java.base/java.text=ALL-UNNAMED',
    '--add-opens', 'java.base/java.time.chrono=ALL-UNNAMED',
    '--add-opens', 'java.base/java.time.format=ALL-UNNAMED',
    '--add-opens', 'java.base/java.time.temporal=ALL-UNNAMED',
    '--add-opens', 'java.base/java.time.zone=ALL-UNNAMED',
    '--add-opens', 'java.base/java.time=ALL-UNNAMED',
    '--add-opens', 'java.base/java.util.concurrent.atomic=ALL-UNNAMED',
    '--add-opens', 'java.base/java.util.concurrent.locks=ALL-UNNAMED',
    '--add-opens', 'java.base/java.util.jar=ALL-UNNAMED',
    '--add-opens', 'java.base/java.util.zip=ALL-UNNAMED',
    '--add-opens', 'java.base/java.util=ALL-UNNAMED',
    '--add-opens', 'java.base/jdk.internal.loader=ALL-UNNAMED',
    '--add-opens', 'java.base/jdk.internal.misc=ALL-UNNAMED',  # ИСПРАВЛЕНО: Добавлен модуль java.base
    '--add-opens', 'java.base/jdk.internal.ref=ALL-UNNAMED',     # ИСПРАВЛЕНО: Добавлен модуль java.base
    '--add-opens', 'java.base/jdk.internal.reflect=ALL-UNNAMED', # ИСПРАВЛЕНО: Добавлен модуль java.base
    '--add-opens', 'java.base/sun.nio.ch=ALL-UNNAMED',           # ИСПРАВЛЕНО: Добавлен модуль java.base
    '--add-opens', 'java.desktop/com.sun.imageio.plugins.png=ALL-UNNAMED',
    '--add-opens', 'java.desktop/sun.awt.image=ALL-UNNAMED',
    '--add-opens', 'java.desktop/sun.awt=ALL-UNNAMED',
    '--add-opens', 'java.desktop/sun.lwawt.macosx=ALL-UNNAMED',
    '--add-opens', 'java.sql.rowset/javax.sql.rowset.serial=ALL-UNNAMED',
    '--add-opens', 'jdk.dynalink/jdk.dynalink.beans=ALL-UNNAMED',
    '--add-opens', 'jdk.naming.dns/com.sun.jndi.dns=ALL-UNNAMED,java.naming',
    '-Dauthlib.debug=true',
    '-XstartOnFirstThread',
    '-Dfml.ignorePatchDiscrepancies=true',
    '-Dfml.ignoreInvalidMinecraftCertificates=true',
    '-Dorg.lwjgl.util.Debug=true',
    '-Dorg.lwjgl.util.DebugLoader=true',
    '-Dorg.lwjgl.util.DebugFunctions=true',
    '-XX:+UnlockExperimentalVMOptions',
    '-XX:+IgnoreUnrecognizedVMOptions',
    '-XX:+UseG1GC',
    '-XX:+UseCompactObjectHeaders',
    '-XX:+AlwaysPreTouch',
    '-XX:+ParallelRefProcEnabled',
    '-XX:+DisableExplicitGC',
    '-XX:+PerfDisableSharedMem',
    '-XX:G1NewSizePercent=30',
    '-XX:G1MaxNewSizePercent=40',
    '-XX:G1ReservePercent=20',
    '-XX:G1HeapWastePercent=5',
    '-XX:MaxGCPauseMillis=50',
    '-XX:G1HeapRegionSize=16M',
    '-XX:MaxTenuringThreshold=1',
    '-XX:+AggressiveOpts',
    '-XX:+DisableAttachMechanism',
    '-Dminecraft.api.env=CUSTOM',
    '-Dminecraft.api.auth=https://auth.mcskill.ru',
    '-Dminecraft.api.auth.host=https://auth.mcskill.ru/sessionserver',
    '-Dminecraft.api.account.host=https://auth.mcskill.ru/sessionserver',
    '-Dminecraft.api.session.host=https://auth.mcskill.ru/sessionserver',
    '-Dminecraft.api.services.host=https://auth.mcskill.ru/sessionserver',
]

def version_ge(v: str, target: str) -> bool:
    def split(ver: str) -> List[int]:
        return [int(x) for x in ver.split('.')]
    a = split(v)
    b = split(target)
    max_len = max(len(a), len(b))
    a += [0] * (max_len - len(a))
    b += [0] * (max_len - len(b))
    return a >= b

def add_client_args(client_profile: ClientProfile, params: Params) -> List[str]:
    p = params.pp
    v = client_profile.version
    args: List[str] = []

    args += ['--username', p.username]

    if version_ge(v, '1.7.2'):
        args += ['--uuid', p.uuid]
        args += ['--accessToken', params.access_token]

        if version_ge(v, '1.7.3'):
            if version_ge(v, '1.7.4'):
                args += ['--userType', 'mojang']

            user_props = {}
            if p.skin:
                user_props['skinURL'] = [p.skin.url]
            if p.cloak:
                user_props['cloakURL'] = [p.cloak.url]

            args += ['--userProperties', json.dumps(user_props)]
            args += ['--assetIndex', client_profile.asset_index]
    else:
        args += ['--session', params.access_token]

    args += ['--version', client_profile.version]
    args += ['--gameDir', str(params.client_dir)]
    args += ['--assetsDir', str(params.asset_dir)]
    args += ['--resourcePackDir', str(params.client_dir / 'resourcepacks')]

    if params.auto_enter and client_profile.server_address:
        args += ['--server', client_profile.server_address]
        args += ['--port', str(client_profile.server_port)]

    if params.full_screen:
        args += ['--fullscreen', 'true']

    if params.width > 0 and params.height > 0:
        args += ['--width', str(params.width)]
        args += ['--height', str(params.height)]

    args += client_profile.client_args
    return args

def build_classpath(client_dir: Path) -> str:
    classpath_file = client_dir / 'classpath.txt'
    jars = []
    for raw in classpath_file.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line:
            continue
        line = line.lstrip('\\').replace('\\', '/')
        jar_path = (client_dir / line).resolve()
        jars.append(str(jar_path))
    return ';'.join(jars)


def launch_minecraft(
    java_path: Path,
    client_profile: ClientProfile,
    params: Params,
    natives_dir: Path,
    classpath: str,
    jvm_memory_mb: int,
    main_class: str = 'com.gtnewhorizons.retrofuturabootstrap.MainStartOnFirstThread',
):
    mc_args = add_client_args(client_profile, params)

    dynamic_jvm_args = [
        f'-Xms{jvm_memory_mb}M',
        f'-Xmx{jvm_memory_mb}M',
        f'-Djava.library.path={natives_dir}',
        f'-Dorg.lwjgl.librarypath={natives_dir}',
    ]

    full_args = [*dynamic_jvm_args, *JVM_ARGS, '-cp', classpath, main_class, *mc_args]
    
    args_file_fd, args_file_path = tempfile.mkstemp(prefix=f'mc-{params.pp.username}-', suffix='.args', text=True)
    with os.fdopen(args_file_fd, 'w', encoding='utf-8') as f:
        for arg in full_args:
            escaped_arg = arg.replace('\\', '\\\\').replace('"', '\\"')
            f.write(f'"{escaped_arg}"\n')

    cmd = [str(java_path), f"@{args_file_path}"]
    print(f'[{params.pp.username}] Запуск... (файл аргументов: {args_file_path})\n')

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8',
        errors='replace',
        bufsize=1
    )

    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                sys.stdout.write(f'[{params.pp.username}] {line}')
            else:
                sys.stdout.write(f'[{params.pp.username}] <no stdout>\n')
    except KeyboardInterrupt:
        proc.kill()
    finally:
        proc.wait()
        try:
            os.remove(args_file_path)
        except OSError:
            pass

def run_all_clients(logins: Dict[str, str], total_ram_mb: int, java_path: Path, client_dir: Path, asset_dir: Path, natives_dir: Path):
    classpath = build_classpath(client_dir)
    n = len(logins)
    ram_per_client = max(512, total_ram_mb // n)
    processes: List[multiprocessing.Process] = []

    for username, password in logins.items():
        result = send_request(username, password)
        errors = {'MFA required': 'Подтвердите вход в телеграмм', 'bad_password': 'Неверный пароль', 'UNKNOWN': 'Неизвестный ответ'}
        if isinstance(result, dict):
            print(f'[{username}] Ошибка входа: {errors.get(result.get('error') or 'UNKNOWN')}')
            continue
        profile, token = result
        skin = Skin(url=f'https://skins.mcskill.net/MinecraftSkins/{profile.username}.png')
        cloak = Cloak(url=f'https://skins.mcskill.net/MinecraftCloaks/{profile.username}.png')
        player = PlayerProfile(username=profile.username, uuid=str(profile.uuid), skin=skin, cloak=cloak)
        client_profile = ClientProfile(version='1.7.10', asset_index='1.7.10', client_args=['--tweakClass', 'cpw.mods.fml.common.launcher.FMLTweaker'])
        params = Params(pp=player, access_token=token, client_dir=client_dir, asset_dir=asset_dir)
        p = multiprocessing.Process(target=launch_minecraft, args=(java_path, client_profile, params, natives_dir, classpath, ram_per_client))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()

def load_config():
    path = Path('config.json')
    DEFAULT_CONFIG = {
        '__comment__path': 'Пути к клиенту',
        'java_path': 'C:\\Users\\User\\McSkill\\java\\25-temurin\\bin\\java.exe',
        'asset_dir': 'C:\\Users\\User\\McSkill\\assets\\assets1.7.10',

        '__comment__ram': 'Общее количество оперативной памяти, выделяемое для всех клиентов.',
        'total_ram_mb': 4096,

        '__comment__accounts': 'Аккаунты указываются в формате: имя_аккаунта:пароль.',
        'accounts': {
            'nick': 'pass'
        },

        "__comment_speed": "Быстрая скорость копания: True/False",
        "mining_speed": False
    }
    if not path.exists():
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
    

def choose_accounts(accounts: dict):
    names = list(accounts.keys())
    if len(names) == 1:
        print(f"Найден один аккаунт: {names[0]}. Запуск автоматически.")
        return [names[0]]
    print("\nВыберите аккаунты для запуска:")
    for i, name in enumerate(names, start=1):
        print(f"{i}. {name}")
    print(f"{len(names)+1}. Все аккаунты")
    print("Введите номера через без пробелов, например: 12 (запустит 1 и 2)")
    choice = input("Ваш выбор: ").strip()
    if choice == str(len(names) + 1):
        return names
    selected = []
    for ch in choice:
        if ch.isdigit():
            idx = int(ch)
            if 1 <= idx <= len(names):
                selected.append(names[idx - 1])
    if not selected:
        print("Ошибка: не выбрано ни одного аккаунта.")
        exit(1)
    return selected


if __name__ == '__main__':
    # updates()
    cfg = load_config()
    if cfg["patcher"]:
        run_patcher(rules)
    multiprocessing.freeze_support() 

    client_dir = Path.cwd()
    natives_dir = client_dir / 'natives25'

    selected_accounts = choose_accounts(cfg['accounts'])

    # run_all_clients(
    #     {acc: cfg['accounts'][acc] for acc in selected_accounts},
    #     cfg['total_ram_mb'],
    #     Path(cfg['java_path']),
    #     client_dir,
    #     Path(cfg['asset_dir']),
    #     natives_dir
    # )

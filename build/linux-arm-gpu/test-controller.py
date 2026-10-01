import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('controller',pathlib.Path(__file__).with_name('controller.py'))
controller = importlib.util.module_from_spec(spec); spec.loader.exec_module(controller)


def packet(slot=0, connected=1, sequence=1, buttons=0, axes=(0,0,0,0,0,0)):
    return controller.PACKET.pack(b'MPG1',slot,connected,0,sequence,buttons,*axes,0)


class FakePad:
    def __init__(self,slot): self.slot=slot; self.closed=False; self.values=[]
    def update(self,buttons,axes): self.values.append((buttons,axes))
    def close(self): self.closed=True


class ControllerTests(unittest.TestCase):
    def test_protocol_fragmentation_resynchronization_and_ranges(self):
        parser=controller.Parser()
        data=packet(buttons=0xf7ff,axes=(-32767,32767,42,-42,0,32767))
        self.assertEqual(parser.feed(b'corrupt'+data[:19]),[])
        self.assertEqual(parser.feed(data[19:]),[controller.decode(data)])
        for bad in (packet(slot=4),packet(connected=2),packet(buttons=0x800),
                    packet(axes=(0,0,0,0,-1,0)),packet(axes=(-32768,0,0,0,0,0)),
                    packet(connected=0,buttons=1)):
            self.assertIsNone(controller.decode(bad))
        parser.feed(b'z'*4096)
        self.assertLess(len(parser.buffer),32)

    def test_real_gamepad_codes_and_analog_values(self):
        events=controller.events(0xf7f9,[-16000,14000,12000,-8000,8192,24576])
        self.assertEqual(len(events),19)
        self.assertEqual(events[-2:],[(3,16,1),(3,17,-1)])
        self.assertEqual(events[11:17],[(3,c,v) for c,v in zip((0,1,3,4,2,5),[-16000,14000,12000,-8000,8192,24576])])
        self.assertTrue(all(value==1 for kind,code,value in events[:11]))

    def test_hotplug_stale_sequences_wraparound_and_watchdog(self):
        pads=controller.Pads(FakePad)
        pads.apply(controller.decode(packet(sequence=0xfffffffe,buttons=0x1000)),0)
        first=pads.devices[0]
        pads.apply(controller.decode(packet(sequence=0xfffffffd)),0.1)
        self.assertEqual(len(first.values),1)
        pads.apply(controller.decode(packet(sequence=0xffffffff)),0.2)
        pads.apply(controller.decode(packet(sequence=0)),0.3)
        self.assertEqual(len(first.values),3)
        pads.expire(2.4)
        self.assertTrue(first.closed); self.assertEqual(pads.mask,0)
        pads.apply(controller.decode(packet(slot=3,sequence=1)),3)
        self.assertEqual(pads.mask,8)
        pads.apply(controller.decode(packet(slot=3,connected=0,sequence=2)),4)
        self.assertEqual(pads.mask,0)
        pads.apply(controller.decode(packet()),5); pads.reset()
        self.assertEqual(pads.mask,0); self.assertEqual(pads.sequences,{})


if __name__=='__main__': unittest.main()

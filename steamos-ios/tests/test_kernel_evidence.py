#!/usr/bin/env python3
"""Reject stale/partial/host-only evidence at the Linux boundary."""
import importlib.util
import json
import pathlib
import unittest

path = pathlib.Path(__file__).resolve().parents[1] / 'tools/run_kernel_gate.py'
spec = importlib.util.spec_from_file_location('kernel_gate', path)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

class EvidenceTests(unittest.TestCase):
    def fixture(self):
        return {'schema': 1, 'run':'test-nonce', 'failures':0, 'kernel':'test-fixture', 'machine':'aarch64',
                'elf_arch':'aarch64','page_bytes':4096,'signals':True,'mmap_protection':True,
                'pthread_tls_futex':True,'fork_exec':True,'checksum':'1d250c45a7bbc87e','wall_ms':1,'cpu_ms':1}
    def log(self, row): return 'MPC_LINUX_ABI ' + json.dumps(row) + '\nMPC_LINUX_EXIT=0\n'
    def test_valid_schema_fixture(self): module.validate(self.log(self.fixture()), 'test-nonce')
    def test_wrong_run(self):
        with self.assertRaises(AssertionError): module.validate(self.log(self.fixture()), 'new-nonce')
    def test_failed_syscall(self):
        for key in ['signals','mmap_protection','pthread_tls_futex','fork_exec']:
            row=self.fixture(); row[key]=False
            with self.assertRaises(AssertionError): module.validate(self.log(row),'test-nonce')
    def test_wrong_arch_checksum(self):
        for key,value in [('machine','x86_64'),('elf_arch','x86_64'),('checksum','0'),('page_bytes',16384)]:
            row=self.fixture(); row[key]=value
            with self.assertRaises(AssertionError): module.validate(self.log(row),'test-nonce')
    def test_duplicate_or_incomplete(self):
        row=self.fixture()
        with self.assertRaises(AssertionError): module.validate(self.log(row)+self.log(row),'test-nonce')
        with self.assertRaises(AssertionError): module.validate(self.log(row).replace('MPC_LINUX_EXIT=0',''),'test-nonce')

if __name__ == '__main__': unittest.main()

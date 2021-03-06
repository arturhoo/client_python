from __future__ import unicode_literals
import os
import threading
import unittest


from prometheus_client import Gauge, Counter, Summary, Histogram, Metric
from prometheus_client import CollectorRegistry, generate_latest, ProcessCollector
from prometheus_client import push_to_gateway, pushadd_to_gateway, delete_from_gateway
from prometheus_client import CONTENT_TYPE_LATEST, instance_ip_grouping_key

try:
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
except ImportError:
    # Python 3
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer



class TestCounter(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Counter('c', 'help', registry=self.registry)

    def test_increment(self):
        self.assertEqual(0, self.registry.get_sample_value('c'))
        self.counter.inc()
        self.assertEqual(1, self.registry.get_sample_value('c'))
        self.counter.inc(7)
        self.assertEqual(8, self.registry.get_sample_value('c'))

    def test_negative_increment_raises(self):
        self.assertRaises(ValueError, self.counter.inc, -1)

    def test_function_decorator(self):
        @self.counter.count_exceptions(ValueError)
        def f(r):
            if r:
                raise ValueError
            else:
                raise TypeError

        try:
            f(False)
        except TypeError:
            pass
        self.assertEqual(0, self.registry.get_sample_value('c'))

        try:
            f(True)
        except ValueError:
            raised = True
        self.assertEqual(1, self.registry.get_sample_value('c'))

    def test_block_decorator(self):
        with self.counter.count_exceptions():
            pass
        self.assertEqual(0, self.registry.get_sample_value('c'))

        raised = False
        try:
            with self.counter.count_exceptions():
                raise ValueError
        except:
            raised = True
        self.assertTrue(raised)
        self.assertEqual(1, self.registry.get_sample_value('c'))


class TestGauge(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.gauge = Gauge('g', 'help', registry=self.registry)

    def test_gauge(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))
        self.gauge.inc()
        self.assertEqual(1, self.registry.get_sample_value('g'))
        self.gauge.dec(3)
        self.assertEqual(-2, self.registry.get_sample_value('g'))
        self.gauge.set(9)
        self.assertEqual(9, self.registry.get_sample_value('g'))

    def test_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))

        @self.gauge.track_inprogress()
        def f():
            self.assertEqual(1, self.registry.get_sample_value('g'))

        f()
        self.assertEqual(0, self.registry.get_sample_value('g'))

    def test_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('g'))
        with self.gauge.track_inprogress():
            self.assertEqual(1, self.registry.get_sample_value('g'))
        self.assertEqual(0, self.registry.get_sample_value('g'))

    def test_gauge_function(self):
        x = {}
        self.gauge.set_function(lambda: len(x))
        self.assertEqual(0, self.registry.get_sample_value('g'))
        self.gauge.inc()
        self.assertEqual(0, self.registry.get_sample_value('g'))
        x['a'] = None
        self.assertEqual(1, self.registry.get_sample_value('g'))


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.summary = Summary('s', 'help', registry=self.registry)

    def test_summary(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        self.assertEqual(0, self.registry.get_sample_value('s_sum'))
        self.summary.observe(10)
        self.assertEqual(1, self.registry.get_sample_value('s_count'))
        self.assertEqual(10, self.registry.get_sample_value('s_sum'))

    def test_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))

        @self.summary.time()
        def f():
            pass

        f()
        self.assertEqual(1, self.registry.get_sample_value('s_count'))

    def test_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('s_count'))
        with self.summary.time():
            pass
        self.assertEqual(1, self.registry.get_sample_value('s_count'))


class TestHistogram(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.histogram = Histogram('h', 'help', registry=self.registry)
        self.labels = Histogram('hl', 'help', ['l'], registry=self.registry)

    def test_histogram(self):
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '1.0'}))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '2.5'}))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_sum'))

        self.histogram.observe(2)
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '1.0'}))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '2.5'}))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(1, self.registry.get_sample_value('h_count'))
        self.assertEqual(2, self.registry.get_sample_value('h_sum'))

        self.histogram.observe(2.5)
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '1.0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '2.5'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(2, self.registry.get_sample_value('h_count'))
        self.assertEqual(4.5, self.registry.get_sample_value('h_sum'))

        self.histogram.observe(float("inf"))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '1.0'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '2.5'}))
        self.assertEqual(2, self.registry.get_sample_value('h_bucket', {'le': '5.0'}))
        self.assertEqual(3, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        self.assertEqual(3, self.registry.get_sample_value('h_count'))
        self.assertEqual(float("inf"), self.registry.get_sample_value('h_sum'))

    def test_setting_buckets(self):
        h = Histogram('h', 'help', registry=None, buckets=[0, 1, 2])
        self.assertEqual([0.0, 1.0, 2.0, float("inf")], h._upper_bounds)

        h = Histogram('h', 'help', registry=None, buckets=[0, 1, 2, float("inf")])
        self.assertEqual([0.0, 1.0, 2.0, float("inf")], h._upper_bounds)

        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=None, buckets=[])
        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=None, buckets=[float("inf")])
        self.assertRaises(ValueError, Histogram, 'h', 'help', registry=None, buckets=[3, 1])

    def test_labels(self):
        self.labels.labels('a').observe(2)
        self.assertEqual(0, self.registry.get_sample_value('hl_bucket', {'le': '1.0', 'l': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('hl_bucket', {'le': '2.5', 'l': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('hl_bucket', {'le': '5.0', 'l': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('hl_bucket', {'le': '+Inf', 'l': 'a'}))
        self.assertEqual(1, self.registry.get_sample_value('hl_count', {'l': 'a'}))
        self.assertEqual(2, self.registry.get_sample_value('hl_sum', {'l': 'a'}))

    def test_function_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))

        @self.histogram.time()
        def f():
            pass

        f()
        self.assertEqual(1, self.registry.get_sample_value('h_count'))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))

    def test_block_decorator(self):
        self.assertEqual(0, self.registry.get_sample_value('h_count'))
        self.assertEqual(0, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))
        with self.histogram.time():
            pass
        self.assertEqual(1, self.registry.get_sample_value('h_count'))
        self.assertEqual(1, self.registry.get_sample_value('h_bucket', {'le': '+Inf'}))


class TestMetricWrapper(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Counter('c', 'help', labelnames=['l'], registry=self.registry)
        self.two_labels = Counter('two', 'help', labelnames=['a', 'b'], registry=self.registry)

    def test_child(self):
        self.counter.labels('x').inc()
        self.assertEqual(1, self.registry.get_sample_value('c', {'l': 'x'}))
        self.two_labels.labels('x', 'y').inc(2)
        self.assertEqual(2, self.registry.get_sample_value('two', {'a': 'x', 'b': 'y'}))

    def test_remove(self):
        self.counter.labels('x').inc()
        self.counter.labels('y').inc(2)
        self.assertEqual(1, self.registry.get_sample_value('c', {'l': 'x'}))
        self.assertEqual(2, self.registry.get_sample_value('c', {'l': 'y'}))
        self.counter.remove('x')
        self.assertEqual(None, self.registry.get_sample_value('c', {'l': 'x'}))
        self.assertEqual(2, self.registry.get_sample_value('c', {'l': 'y'}))

    def test_incorrect_label_count_raises(self):
        self.assertRaises(ValueError, self.counter.labels)
        self.assertRaises(ValueError, self.counter.labels, 'a', 'b')
        self.assertRaises(ValueError, self.counter.remove)
        self.assertRaises(ValueError, self.counter.remove, 'a', 'b')

    def test_labels_coerced_to_string(self):
        self.counter.labels(None).inc()
        self.counter.labels({'l': None}).inc()
        self.assertEqual(2, self.registry.get_sample_value('c', {'l': 'None'}))

        self.counter.remove(None)
        self.assertEqual(None, self.registry.get_sample_value('c', {'l': 'None'}))

    def test_non_string_labels_raises(self):
        class Test(object):
            __str__ = None
        self.assertRaises(TypeError, self.counter.labels, Test())
        self.assertRaises(TypeError, self.counter.labels, {'l': Test()})

    def test_namespace_subsystem_concatenated(self):
        c = Counter('c', 'help', namespace='a', subsystem='b', registry=self.registry)
        c.inc()
        self.assertEqual(1, self.registry.get_sample_value('a_b_c'))

    def test_labels_by_dict(self):
        self.counter.labels({'l': 'x'}).inc()
        self.assertEqual(1, self.registry.get_sample_value('c', {'l': 'x'}))
        self.assertRaises(ValueError, self.counter.labels, {'l': 'x', 'm': 'y'})
        self.assertRaises(ValueError, self.counter.labels, {'m': 'y'})
        self.assertRaises(ValueError, self.counter.labels, {})
        self.two_labels.labels({'a': 'x', 'b': 'y'}).inc()
        self.assertEqual(1, self.registry.get_sample_value('two', {'a': 'x', 'b': 'y'}))
        self.assertRaises(ValueError, self.two_labels.labels, {'a': 'x', 'b': 'y', 'c': 'z'})
        self.assertRaises(ValueError, self.two_labels.labels, {'a': 'x', 'c': 'z'})
        self.assertRaises(ValueError, self.two_labels.labels, {'b': 'y', 'c': 'z'})
        self.assertRaises(ValueError, self.two_labels.labels, {'c': 'z'})
        self.assertRaises(ValueError, self.two_labels.labels, {})

    def test_invalid_names_raise(self):
        self.assertRaises(ValueError, Counter, '', 'help')
        self.assertRaises(ValueError, Counter, '^', 'help')
        self.assertRaises(ValueError, Counter, '', 'help', namespace='&')
        self.assertRaises(ValueError, Counter, '', 'help', subsystem='(')
        self.assertRaises(ValueError, Counter, 'c', '', labelnames=['^'])
        self.assertRaises(ValueError, Counter, 'c', '', labelnames=['__reserved'])
        self.assertRaises(ValueError, Summary, 'c', '', labelnames=['quantile'])


class TestGenerateText(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()

    def test_counter(self):
        c = Counter('cc', 'A counter', registry=self.registry)
        c.inc()
        self.assertEqual(b'# HELP cc A counter\n# TYPE cc counter\ncc 1.0\n', generate_latest(self.registry))

    def test_gauge(self):
        g = Gauge('gg', 'A gauge', registry=self.registry)
        g.set(17)
        self.assertEqual(b'# HELP gg A gauge\n# TYPE gg gauge\ngg 17.0\n', generate_latest(self.registry))

    def test_summary(self):
        s = Summary('ss', 'A summary', ['a', 'b'], registry=self.registry)
        s.labels('c', 'd').observe(17)
        self.assertEqual(b'# HELP ss A summary\n# TYPE ss summary\nss_count{a="c",b="d"} 1.0\nss_sum{a="c",b="d"} 17.0\n', generate_latest(self.registry))

    def test_unicode(self):
        c = Counter('cc', '\u4500', ['l'], registry=self.registry)
        c.labels('\u4500').inc()
        self.assertEqual(b'# HELP cc \xe4\x94\x80\n# TYPE cc counter\ncc{l="\xe4\x94\x80"} 1.0\n', generate_latest(self.registry))

    def test_escaping(self):
        c = Counter('cc', 'A\ncount\\er', ['a'], registry=self.registry)
        c.labels('\\x\n"').inc(1)
        self.assertEqual(b'# HELP cc A\\ncount\\\\er\n# TYPE cc counter\ncc{a="\\\\x\\n\\""} 1.0\n', generate_latest(self.registry))

    def test_nonnumber(self):
        class MyNumber():
            def __repr__(self):
              return "MyNumber(123)"
            def __float__(self):
              return 123.0
        class MyCollector():
            def collect(self):
                metric = Metric("nonnumber", "Non number", 'untyped')
                metric.add_sample("nonnumber", {}, MyNumber())
                yield metric
        self.registry.register(MyCollector())
        self.assertEqual(b'# HELP nonnumber Non number\n# TYPE nonnumber untyped\nnonnumber 123.0\n', generate_latest(self.registry))


class TestProcessCollector(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.test_proc = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'proc')

    def test_working(self):
        collector = ProcessCollector(proc=self.test_proc, pid=lambda: 26231, registry=self.registry)
        collector._ticks = 100

        self.assertEqual(17.21, self.registry.get_sample_value('process_cpu_seconds_total'))
        self.assertEqual(56274944.0, self.registry.get_sample_value('process_virtual_memory_bytes'))
        self.assertEqual(8114176, self.registry.get_sample_value('process_resident_memory_bytes'))
        self.assertEqual(1418184099.75, self.registry.get_sample_value('process_start_time_seconds'))
        self.assertEqual(2048.0, self.registry.get_sample_value('process_max_fds'))
        self.assertEqual(5.0, self.registry.get_sample_value('process_open_fds'))
        self.assertEqual(None, self.registry.get_sample_value('process_fake_namespace'))

    def test_namespace(self):
        collector = ProcessCollector(proc=self.test_proc, pid=lambda: 26231, registry=self.registry, namespace='n')
        collector._ticks = 100

        self.assertEqual(17.21, self.registry.get_sample_value('n_process_cpu_seconds_total'))
        self.assertEqual(56274944.0, self.registry.get_sample_value('n_process_virtual_memory_bytes'))
        self.assertEqual(8114176, self.registry.get_sample_value('n_process_resident_memory_bytes'))
        self.assertEqual(1418184099.75, self.registry.get_sample_value('n_process_start_time_seconds'))
        self.assertEqual(2048.0, self.registry.get_sample_value('n_process_max_fds'))
        self.assertEqual(5.0, self.registry.get_sample_value('n_process_open_fds'))
        self.assertEqual(None, self.registry.get_sample_value('process_cpu_seconds_total'))

    def test_working_584(self):
        collector = ProcessCollector(proc=self.test_proc, pid=lambda: "584\n", registry=self.registry)
        collector._ticks = 100

        self.assertEqual(0.0, self.registry.get_sample_value('process_cpu_seconds_total'))
        self.assertEqual(10395648.0, self.registry.get_sample_value('process_virtual_memory_bytes'))
        self.assertEqual(634880, self.registry.get_sample_value('process_resident_memory_bytes'))
        self.assertEqual(1418291667.75, self.registry.get_sample_value('process_start_time_seconds'))
        self.assertEqual(None, self.registry.get_sample_value('process_max_fds'))
        self.assertEqual(None, self.registry.get_sample_value('process_open_fds'))

    def test_working_fake_pid(self):
        collector = ProcessCollector(proc=self.test_proc, pid=lambda: 123, registry=self.registry)
        collector._ticks = 100

        self.assertEqual(None, self.registry.get_sample_value('process_cpu_seconds_total'))
        self.assertEqual(None, self.registry.get_sample_value('process_virtual_memory_bytes'))
        self.assertEqual(None, self.registry.get_sample_value('process_resident_memory_bytes'))
        self.assertEqual(None, self.registry.get_sample_value('process_start_time_seconds'))
        self.assertEqual(None, self.registry.get_sample_value('process_max_fds'))
        self.assertEqual(None, self.registry.get_sample_value('process_open_fds'))
        self.assertEqual(None, self.registry.get_sample_value('process_fake_namespace'))


class TestPushGateway(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.counter = Gauge('g', 'help', registry=self.registry)
        self.requests = requests = []
        class TestHandler(BaseHTTPRequestHandler):
            def do_PUT(self):
                self.send_response(201)
                length = int(self.headers['content-length'])
                requests.append((self, self.rfile.read(length)))

            do_POST = do_PUT
            do_DELETE = do_PUT

        httpd = HTTPServer(('', 0), TestHandler)
        self.address = ':'.join([str(x) for x in httpd.server_address])
        class TestServer(threading.Thread):
            def run(self):
                httpd.handle_request()
        self.server = TestServer()
        self.server.daemon = True
        self.server.start()

    def test_push(self):
        push_to_gateway(self.address, "my_job", self.registry)
        self.assertEqual(self.requests[0][0].command, 'PUT')
        self.assertEqual(self.requests[0][0].path, '/job/my_job')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_push_with_groupingkey(self):
        push_to_gateway(self.address, "my_job", self.registry, {'a': 9})
        self.assertEqual(self.requests[0][0].command, 'PUT')
        self.assertEqual(self.requests[0][0].path, '/job/my_job/a/9')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_push_with_complex_groupingkey(self):
        push_to_gateway(self.address, "my_job", self.registry, {'a': 9, 'b': 'a/ z'})
        self.assertEqual(self.requests[0][0].command, 'PUT')
        self.assertEqual(self.requests[0][0].path, '/job/my_job/a/9/b/a%2F+z')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_pushadd(self):
        pushadd_to_gateway(self.address, "my_job", self.registry)
        self.assertEqual(self.requests[0][0].command, 'POST')
        self.assertEqual(self.requests[0][0].path, '/job/my_job')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_pushadd_with_groupingkey(self):
        pushadd_to_gateway(self.address, "my_job", self.registry, {'a': 9})
        self.assertEqual(self.requests[0][0].command, 'POST')
        self.assertEqual(self.requests[0][0].path, '/job/my_job/a/9')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'# HELP g help\n# TYPE g gauge\ng 0.0\n')

    def test_delete(self):
        delete_from_gateway(self.address, "my_job")
        self.assertEqual(self.requests[0][0].command, 'DELETE')
        self.assertEqual(self.requests[0][0].path, '/job/my_job')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'')

    def test_pushadd_with_groupingkey(self):
        delete_from_gateway(self.address, "my_job", {'a': 9})
        self.assertEqual(self.requests[0][0].command, 'DELETE')
        self.assertEqual(self.requests[0][0].path, '/job/my_job/a/9')
        self.assertEqual(self.requests[0][0].headers.get('content-type'), CONTENT_TYPE_LATEST)
        self.assertEqual(self.requests[0][1], b'')

    def test_instance_ip_grouping_key(self):
        self.assertTrue('' != instance_ip_grouping_key()['instance'])


if __name__ == '__main__':
    unittest.main()

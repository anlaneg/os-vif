# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import contextlib
import mock
import six
import testtools

import fixtures
from oslo_concurrency import lockutils
from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_config import fixture as config_fixture
from oslo_log.fixture import logging_error as log_fixture

from vif_plug_linux_bridge import linux_net
from vif_plug_linux_bridge import privsep

CONF = cfg.CONF

if six.PY2:
    nested = contextlib.nested
else:
    @contextlib.contextmanager
    def nested(*contexts):
        with contextlib.ExitStack() as stack:
            yield [stack.enter_context(c) for c in contexts]


class LinuxNetTest(testtools.TestCase):

    def setUp(self):
        super(LinuxNetTest, self).setUp()

        privsep.vif_plug.set_client_mode(False)
        lock_path = self.useFixture(fixtures.TempDir()).path
        self.fixture = self.useFixture(
            config_fixture.Config(lockutils.CONF))
        self.fixture.config(lock_path=lock_path,
                            group='oslo_concurrency')
        self.useFixture(log_fixture.get_logging_handle_error_fixture())

    @mock.patch.object(processutils, "execute")
    def test_set_device_mtu(self, execute):
        linux_net._set_device_mtu(dev='fakedev', mtu=1500)
        expected = ['ip', 'link', 'set', 'fakedev', 'mtu', 1500]
        execute.assert_called_with(*expected, check_exit_code=mock.ANY)

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    @mock.patch.object(linux_net, "_set_device_mtu")
    def test_ensure_vlan(self, mock_set_mtu,
                         mock_dev_exists, mock_exec):
        linux_net._ensure_vlan_privileged(123, 'fake-bridge',
                                          mac_address='fake-mac',
                                          mtu=1500)
        self.assertTrue(mock_dev_exists.called)
        calls = [mock.call('ip', 'link', 'add', 'link',
                           'fake-bridge', 'name', 'vlan123', 'type',
                           'vlan', 'id', 123,
                           check_exit_code=[0, 2, 254]),
                 mock.call('ip', 'link', 'set', 'vlan123',
                           'address', 'fake-mac',
                           check_exit_code=[0, 2, 254]),
                 mock.call('ip', 'link', 'set', 'vlan123', 'up',
                           check_exit_code=[0, 2, 254])]
        self.assertEqual(calls, mock_exec.mock_calls)
        mock_set_mtu.assert_called_once_with('vlan123', 1500)

    @mock.patch.object(processutils, "execute")
    @mock.patch.object(linux_net, "device_exists", return_value=False)
    @mock.patch.object(linux_net, "_set_device_mtu")
    def test_ensure_vlan_invalid_mtu(self, mock_set_mtu,
                                     mock_dev_exists, mock_exec):
        linux_net._ensure_vlan_privileged(123, 'fake-bridge',
                                          mac_address='fake-mac', mtu=None)
        self.assertFalse(mock_set_mtu.called)
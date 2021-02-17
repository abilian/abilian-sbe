from blinker.base import Namespace

# pylint: disable=C0103
#         invalid constant name

ns = Namespace()

#: sent when membership is set. Sender is community, arguments are:
#: :class:`.models.Membership` instance, :bool:`is_new`
membership_set = ns.signal("membership_set")

#: sent just before membership is removed. Sender is community, arguments:
# :class:`.models.Membership` instance
membership_removed = ns.signal("membership_removed")

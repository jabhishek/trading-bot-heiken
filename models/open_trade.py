from dateutil import parser

class OpenTrade:

    def __init__(self, api_ob):
        self.id = api_ob['id']
        self.instrument = api_ob['instrument']
        self.state = api_ob['state']
        self.price = float(api_ob['price'])
        self.currentUnits = float(api_ob['currentUnits'])
        self.unrealizedPL = float(api_ob.get('unrealizedPL', '0'))
        self.marginUsed = float(api_ob.get('marginUsed', '0'))
        self.trailingStopLossOrder = api_ob.get('trailingStopLossOrder', None)
        self.stopLossOrder = api_ob.get('stopLossOrder', None)

    def __repr__(self):
        return str(vars(self))
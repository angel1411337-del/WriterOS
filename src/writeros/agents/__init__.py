from .theorist import TheoristAgent
from .profiler import ProfilerAgent
from .navigator import NavigatorAgent  # <--- NEW
from .chronologist import ChronologistAgent
from .psychologist import PsychologistAgent
from .dramatist import DramatistAgent
from .architect import ArchitectAgent
from .stylist import StylistAgent
from .mechanic import MechanicAgent
from .producer import ProducerAgent    # <--- NEW (If you added the PM)

class AgentSwarm:
    def __init__(self, model_name="gpt-5.1"):
        self.theorist = TheoristAgent(model_name)
        self.profiler = ProfilerAgent(model_name)
        self.navigator = NavigatorAgent(model_name) # <--- NEW
        self.chronologist = ChronologistAgent(model_name)
        self.psychologist = PsychologistAgent(model_name)
        self.dramatist = DramatistAgent(model_name)
        self.architect = ArchitectAgent(model_name)
        self.stylist = StylistAgent(model_name)
        self.mechanic = MechanicAgent(model_name)
        self.producer = ProducerAgent(model_name)   # <--- NEW
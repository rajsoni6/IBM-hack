from .health import health_bp
from .auth import auth_bp
from .cases import cases_bp
from .intelligence import intelligence_bp
from .ai_extraction import ai_bp
from .graph import graph_bp
from .patterns import patterns_bp
from .predict import predict_bp
from .timeline import timeline_bp
from .evidence import evidence_bp
from .summary import summary_bp

ALL_BLUEPRINTS = [
    health_bp, auth_bp, cases_bp, intelligence_bp, ai_bp,
    graph_bp, patterns_bp, predict_bp,
    timeline_bp, evidence_bp, summary_bp,
]

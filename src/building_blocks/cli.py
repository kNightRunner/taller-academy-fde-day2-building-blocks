"""Reusable CLI parsing for the three labs."""
import argparse
from .providers import create_provider


def parser(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--provider", choices=["ollama", "anthropic"], default="ollama")
    p.add_argument("--model", default=None)
    p.add_argument("--temperature", type=float, default=0.1)
    return p


def from_args(args):
    return create_provider(args.provider, args.model, args.temperature)

import sys
import os
from sqlmodel import Session, select
from writeros.utils.db import engine
from writeros.schema.agent_execution import AgentCitation, AgentExecution

def verify_citations():
    print("Verifying citations in database...")
    with Session(engine) as session:
        # Get the most recent execution
        execution = session.exec(
            select(AgentExecution)
            .order_by(AgentExecution.started_at.desc())
            .limit(1)
        ).first()
        
        if not execution:
            print("No executions found.")
            return

        print(f"Checking execution {execution.id} ({execution.agent_method})...")
        
        citations = session.exec(
            select(AgentCitation)
            .where(AgentCitation.execution_id == execution.id)
        ).all()
        
        if not citations:
            print("No citations found for this execution.")
            # Check if synthesis contained citations but they weren't parsed
            if execution.output_data:
                print("Output data preview:", str(execution.output_data)[:200])
            return

        print(f"Found {len(citations)} citations:")
        for i, citation in enumerate(citations, 1):
            print(f"{i}. [{citation.source_type}] {citation.quote}")
            print(f"   Source ID: {citation.source_id}")

if __name__ == "__main__":
    verify_citations()

from app.memory.session import SessionManager


def test_session_manager_tracks_user_id_and_agent_id():
    manager = SessionManager()
    manager.start(agent_id="agent-123", user_id="AOS-7F29K4")

    metadata = manager.metadata()

    assert metadata["user_id"] == "AOS-7F29K4"
    assert metadata["agent_id"] == "agent-123"
    assert metadata["session_id"]

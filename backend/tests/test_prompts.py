from app.prompts import SOAP_NOTE_SYSTEM_PROMPT, SOAP_NOTE_USER_PROMPT


def test_soap_prompt_forbids_inference_and_icd_recall():
    prompt = SOAP_NOTE_SYSTEM_PROMPT.lower()
    assert "only state what is directly present" in prompt
    assert "do not infer" in prompt
    assert "leave it out" in prompt
    assert "omit it" in prompt
    assert "do not emit icd-10 codes" in prompt
    assert "never assert a symptom" in prompt
    assert "only asked about" in prompt
    assert "denied" in prompt
    assert "left unconfirmed" in prompt
    assert "likely_diagnoses" in SOAP_NOTE_USER_PROMPT
    assert "citations" in SOAP_NOTE_USER_PROMPT
    assert "suggested_icd10" not in SOAP_NOTE_USER_PROMPT

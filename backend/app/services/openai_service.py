# backend/app/services/openai_service.py
# ============================================================
# OpenAI API service — reused from your Streamlit project
# Same error handling, same logic, just returns APIResponse
# ============================================================

from openai import OpenAI, AuthenticationError, RateLimitError, APIError
from app.config import settings
from app.models.schemas import APIResponse
from app.services.prompts import build_journal_prompt, build_term_prompt


def _get_client() -> OpenAI | None:
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-여기에"):
        return None
    return OpenAI(api_key=settings.openai_api_key)


def _call_openai(system_prompt: str, user_message: str) -> APIResponse:
    client = _get_client()
    if client is None:
        return APIResponse(
            success=False,
            error="API 키가 설정되지 않았습니다. backend/.env 파일을 확인해주세요.",
        )

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
        )
        return APIResponse(success=True, content=response.choices[0].message.content)

    except RateLimitError:
        return APIResponse(success=False, error="API 사용 한도를 초과했습니다. OpenAI 결제 상태를 확인해주세요.")

    except AuthenticationError:
        return APIResponse(success=False, error="API 키가 유효하지 않습니다. .env 파일을 확인해주세요.")

    except APIError as e:
        return APIResponse(success=False, error=f"OpenAI 서버 오류 (코드: {e.status_code}). 잠시 후 다시 시도해주세요.")

    except Exception as e:
        return APIResponse(success=False, error=f"연결 오류: {type(e).__name__}")


def get_journal_entry(transaction: str, lang: str) -> APIResponse:
    return _call_openai(build_journal_prompt(lang), transaction)


def get_term_explanation(term: str, lang: str) -> APIResponse:
    return _call_openai(build_term_prompt(lang), term)

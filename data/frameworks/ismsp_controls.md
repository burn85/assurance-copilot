# ISMS-P Control Catalog — Access Authorization & Access Control (2.5–2.6)

> Paraphrased summaries of public ISMS-P certification criteria, for demo use only.
> These are **not** the official normative texts. Format is parsed by
> `retrieval/local_retriever.py`: one control per `## <id> — <title>` heading,
> with `**Requirement:**` and `**Guidance:**` bullets.

## ISMS-P 2.5.1 — User Account Management (사용자 계정 관리)
- **Requirement:** 정보시스템 및 개인정보처리시스템에 대한 사용자 계정의 등록·변경·삭제를 공식 승인 절차에 따라 관리하고, 입사·직무변경·퇴직 등 인사 이벤트에 연동하여 계정과 권한을 적시에 부여·회수하며 그 이력을 남긴다.
- **Guidance:** 계정 생성 및 권한 부여에 대한 책임자 승인 기록이 존재하는가. 퇴직·전보 시 접근권한이 지체 없이 회수되는가. 계정·권한 목록이 인사 현황과 정기적으로 대사되는가.

## ISMS-P 2.5.3 — User Authentication (사용자 인증)
- **Requirement:** 정보시스템 접근 시 사용자의 신원을 인증 절차로 확인하고, 인증 실패 횟수 제한·세션 관리 등으로 비인가 접근을 통제한다. 중요 시스템·외부 접속에는 강화된 인증(예: 다중요소 인증)을 적용한다.
- **Guidance:** 로그인 실패 임계치와 계정 잠금이 설정되어 있는가. 관리자·원격 접근에 다중요소 인증이 적용되는가. 인증정보가 안전하게 전송·저장되는가.

## ISMS-P 2.5.4 — Password Management (비밀번호 관리)
- **Requirement:** 사용자 및 이용자 비밀번호에 대해 복잡도·변경주기·재사용 제한 등 관리 기준을 수립·적용하고, 비밀번호를 안전한 방식으로 저장한다.
- **Guidance:** 비밀번호 정책(길이·복잡도·이력)이 시스템에 강제되는가. 비밀번호가 평문이 아닌 해시 등 안전한 형태로 저장되는가. 초기·임시 비밀번호의 변경이 강제되는가.

## ISMS-P 2.5.5 — Privileged Account & Authorization Management (특수 계정 및 권한 관리)
- **Requirement:** 관리자·특수 권한 계정을 최소한으로 식별·관리하고, 부여 사유와 승인 근거를 문서화하며, 일반 계정과 분리하여 사용·감사한다.
- **Guidance:** 특수 권한이 최소 인원에게만 부여되고 사유가 기록되는가. 공용 관리자 계정 사용을 지양하고 개인별로 식별되는가. 특수 계정 활동이 로깅·검토되는가.

## ISMS-P 2.5.6 — Access Rights Review (접근권한 검토)
- **Requirement:** 사용자 계정과 접근권한의 적정성을 정기적으로 검토하고, 과도하거나 불필요한 권한을 발견하면 조정·회수한다. 검토 주기·방법·책임자를 정한다.
- **Guidance:** 접근권한 검토가 정해진 주기로 수행되고 결과가 기록되는가. 발견된 과다 권한이 실제로 회수되었는가. 검토 대상에 특수 권한·휴면 계정이 포함되는가.

## ISMS-P 2.6.1 — Network Access Control (네트워크 접근)
- **Requirement:** 네트워크를 업무·중요도에 따라 분리하고, 접근이 허용된 사용자·기기·서비스만 접속하도록 통제한다. 외부와 내부 네트워크 간 접근은 방화벽 등으로 제한한다.
- **Guidance:** 네트워크 대역이 목적에 따라 분리되어 있는가. 방화벽 정책이 최소 권한 원칙으로 구성되고 주기적으로 검토되는가. 비인가 단말의 내부망 접속이 차단되는가.

## ISMS-P 2.6.2 — Information System Access Control (정보시스템 접근)
- **Requirement:** 서버·정보시스템에 대한 접근을 업무상 필요한 계정으로 제한하고, 접근 수단(콘솔·원격 등)과 경로를 통제하며 접근 기록을 남긴다.
- **Guidance:** 시스템 접근이 최소 권한으로 제한되는가. 원격 관리 접근이 통제된 경로·인증을 거치는가. 접근·명령 실행 로그가 수집·보존되는가.

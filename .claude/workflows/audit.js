export const meta = {
  name: 'audit',
  description: '설계서·코드·테스트·보안을 관점별 에이전트가 병렬로 감사하고, 반박 검증을 통과한 지적만 남긴다',
  whenToUse: 'PR 을 올리기 전, 또는 설계서를 크게 고친 뒤. "감사 돌려줘", "정합성 검사해줘" 같은 요청에.',
  phases: [
    { title: '감사', detail: '관점마다 읽기 전용 에이전트 하나' },
    { title: '반박 검증', detail: '지적마다 반박을 시도하는 에이전트 하나' },
  ],
}

// 마스터(이 스크립트)는 관점을 나눠 배정하고 결과를 모아 판단한다.
// 서브 에이전트는 한 관점만 보고, 파일을 고치지 않고, 근거와 함께 지적만 낸다.
// 지적은 반박 검증을 한 번 더 거친다 — 그럴듯하지만 틀린 지적을 걸러 낸다.
// 고칠지는 사람이 정한다. 이 워크플로우는 아무것도 고치지 않는다.

// 저장소 위치. 저장소 안에서 돌리면 생략한다. 다른 곳에서 돌리면 args.root 로 넘긴다.
const ROOT = (args && args.root) || '.'
const READ_ONLY = `저장소는 ${ROOT} 이고, 아래 경로는 모두 이 저장소 기준이다.
파일을 절대 고치지 마라. 읽기만 하고 근거(파일:줄)와 함께 보고하라. 확신이 없으면 지적하지 마라.`

const LENSES = [
  {
    key: 'requirements',
    prompt: `docs/requirements.md 의 FR · NFR 가 docs/design/ 설계서에서 실제로 충족되는지 감사하라.
배정만 되고 어느 흐름 · 규칙도 다루지 않는 요구사항, 반대로 요구사항에 근거가 없는 설계를 찾아라.`,
  },
  {
    key: 'design-vs-code',
    prompt: `docs/design/query.md 의 흐름(2.1) · 질의 단계(2.2) · 규칙(3절) · 모델과 의존(5.1 · 5.2) · 설정(5.3)과 backend/app/ 코드가 일치하는지 감사하라.
설계서에 없는 동작이 코드에 있거나, 설계서의 규칙이 코드에서 다르게 구현된 곳을 찾아라.`,
  },
  {
    key: 'tests',
    prompt: `backend/tests/ 가 .claude/rules/backend-test.md 를 지키는지, 설계서 4절 테스트 사항을 실제로 확인하는지 감사하라.
규칙 ID 만 적고 그 사실을 확인하지 않는 테스트, 어떤 값이 와도 통과하는 단언, 구현에 기대는 테스트를 찾아라.`,
  },
  {
    key: 'security',
    prompt: `데이터를 바꾸는 SQL 이 실행될 수 있는 경로를 공격자 관점에서 찾아라 (NFR-001).
backend/app/query/rules/ 의 판정(QRY-R002 ~ QRY-R005)과 SQL 분석기를 우회할 SQL, 읽기 전용 연결을 벗어날 방법, 프롬프트 인젝션으로 내부 표를 노출시킬 방법을 시도하라.
추측이 아니라 실제로 통과할 SQL 문자열을 근거로 내라.`,
  },
]

const FINDINGS = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          where: { type: 'string', description: '파일:줄' },
          evidence: { type: 'string' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['title', 'where', 'evidence', 'severity'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string' },
  },
  required: ['refuted', 'reason'],
}

const results = await pipeline(
  LENSES,
  (lens) =>
    agent(`${lens.prompt}\n\n${READ_ONLY}`, {
      label: `감사:${lens.key}`,
      phase: '감사',
      schema: FINDINGS,
    }),
  (found, lens) =>
    parallel(
      (found?.findings ?? []).map((f) => () =>
        agent(
          `다음 지적을 반박하라. 코드와 문서를 직접 읽고, 지적이 틀렸거나 과장됐으면 refuted=true.
확인할 수 없으면 refuted=true 로 둔다.\n\n관점: ${lens.key}\n지적: ${f.title}\n위치: ${f.where}\n근거: ${f.evidence}\n\n${READ_ONLY}`,
          { label: `검증:${lens.key}`, phase: '반박 검증', schema: VERDICT },
        ).then((v) => ({ ...f, lens: lens.key, verdict: v })),
      ),
    ),
)

const all = results.filter(Boolean).flat().filter(Boolean)
const confirmed = all.filter((f) => f.verdict && !f.verdict.refuted)
log(`지적 ${all.length}건 중 반박을 견딘 것 ${confirmed.length}건`)

const order = { high: 0, medium: 1, low: 2 }
return confirmed
  .sort((a, b) => order[a.severity] - order[b.severity])
  .map(({ lens, severity, title, where, evidence }) => ({ lens, severity, title, where, evidence }))

import { describe, expect, it } from 'vitest'
import Ajv from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import schema from '../contracts/openapi.json'
import { staticApi } from '../src/api/staticClient'
import { DEMO_DATE } from '../src/lib/format'

const ajv = new Ajv({ strict: false, allErrors: true })
addFormats(ajv)
// Pydantic time fields serialize ISO local times, without a mandatory UTC offset.
ajv.addFormat('time', addFormats.get('iso-time'))
function validate(name: keyof typeof schema.components.schemas, value: unknown) {
  const check = ajv.compile({ $ref: `#/components/schemas/${name}`, components: schema.components })
  expect(check(value), JSON.stringify(check.errors)).toBe(true)
}
describe('fixture payloads against backend-generated OpenAPI', () => {
  it('validates catalog and schedule payloads', async () => {
    for (const item of await staticApi.getGroups()) validate('GroupRead', item)
    for (const item of await staticApi.getTeachers()) validate('TeacherRead', item)
    for (const item of await staticApi.getClassrooms()) validate('ClassroomRead', item)
    for (const item of await staticApi.getDisciplines()) validate('DisciplineRead', item)
    for (const item of await staticApi.getSchedule()) validate('ScheduleRead', item)
  })
  it('validates sessions, measurements, recognition and media', async () => {
    for (const session of await staticApi.getSessions(DEMO_DATE)) {
      validate('app__schemas__session__SessionRead', session)
      validate('SessionDetail', await staticApi.getSession(session.id))
    }
    for (const upload of await staticApi.getRecognitionUploads()) {
      validate('RecognitionUploadRead', upload)
      validate('RecognitionUploadMediaRead', await staticApi.getRecognitionUploadMedia(upload.id))
    }
    validate('RecognitionEvaluationSummary', await staticApi.getRecognitionEvaluationSummary())
  })
  it('validates summary, breakdown, and timeline contracts', async () => {
    validate('SummaryStats', await staticApi.getSummary())
    for (const group of await staticApi.getGroups()) {
      validate('EntityStats', await staticApi.getGroupStats(group.id))
      validate('GroupTimeline', await staticApi.getGroupTimeline(group.id))
    }
    validate('WeekTypeRead', await staticApi.getWeekType(DEMO_DATE))
  })
})

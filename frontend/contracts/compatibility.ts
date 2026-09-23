import type { components, paths } from '../src/api/generated'
import type * as UI from '../src/api/types'
import type { User } from '../src/auth/SessionProvider'
import type { ManagedUser, AuditEvent, SystemStatus, Capabilities, managementApi } from '../src/api/management'
import type { api } from '../src/api/client'
import type { staticApi } from '../src/api/staticClient'
import type * as normalize from '../src/api/normalize'

type Schema = components['schemas']
type Assert<T extends true> = T
// Wire responses with nullable/defaulted fields pass through generated-type normalizers.
// The normalizer implementations themselves must compile against the current schema.
type ReadContracts = [
  Assert<ReturnType<typeof normalize.group> extends UI.Group ? true : false>,
  Assert<ReturnType<typeof normalize.teacher> extends UI.Teacher ? true : false>,
  Assert<Schema['DisciplineRead'] extends UI.Discipline ? true : false>,
  Assert<ReturnType<typeof normalize.camera> extends UI.Camera ? true : false>,
  Assert<ReturnType<typeof normalize.classroom> extends UI.Classroom ? true : false>,
  Assert<ReturnType<typeof normalize.schedule> extends UI.ScheduleItem ? true : false>,
  Assert<ReturnType<typeof normalize.session> extends UI.Session ? true : false>,
  Assert<ReturnType<typeof normalize.sessionDetail> extends UI.SessionDetail ? true : false>,
  Assert<Schema['RecognitionResultRead'] extends UI.RecognitionResult ? true : false>,
  Assert<ReturnType<typeof normalize.upload> extends UI.RecognitionUpload ? true : false>,
  Assert<Schema['RecognitionUploadMediaRead'] extends UI.RecognitionUploadMedia ? true : false>,
  Assert<Schema['RecognitionEvaluationSummary'] extends UI.RecognitionEvaluationSummary ? true : false>,
  Assert<Schema['SummaryStats'] extends UI.SummaryStats ? true : false>,
  Assert<Schema['EntityStats'] extends UI.EntityStats ? true : false>,
  Assert<Schema['GroupTimeline'] extends UI.GroupTimeline ? true : false>,
  Assert<Schema['ScheduleImportResult'] extends UI.ImportResult ? true : false>,
  Assert<Schema['UserRead'] extends ManagedUser ? true : false>,
  Assert<Schema['AuditRead'] extends AuditEvent ? true : false>,
  Assert<Schema['app__api__v1__auth__SessionRead'] extends User ? true : false>,
  Assert<Schema['SystemRead'] extends SystemStatus ? true : false>,
  Assert<Schema['RecognitionCapabilities'] extends Capabilities ? true : false>,
  Assert<ReturnType<typeof normalize.importPreview> extends UI.ImportPreview ? true : false>,
  Assert<ReturnType<typeof normalize.recognitionHistory> extends UI.RecognitionHistory ? true : false>,
  Assert<Schema['CorrectionCreated'] extends Awaited<ReturnType<typeof managementApi.correct>> ? true : false>,
]
type DemoContract = Assert<typeof staticApi extends typeof api ? true : false>
type LoginBody = paths['/api/v1/auth/login']['post']['requestBody']['content']['application/json']
type LoginContract = Assert<{ username: string; password: string } extends LoginBody ? true : false>
type UploadBody = paths['/api/v1/recognition/uploads']['post']['requestBody']['content']['multipart/form-data']
type UploadFields = Assert<'file' | 'session_id' | 'measurement_id' | 'confidence_threshold' | 'sample_rate_fps' extends keyof UploadBody ? true : false>

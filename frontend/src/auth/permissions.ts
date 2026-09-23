export type Role = 'admin' | 'operator' | 'teacher' | 'analyst'
export const roleLabels: Record<Role, string> = {
  admin: 'Администратор', operator: 'Оператор', teacher: 'Преподаватель', analyst: 'Аналитик',
}
export const homeForRole: Record<Role, string> = {
  admin: '/', operator: '/recognition', teacher: '/sessions', analyst: '/analytics',
}
export function mayVisit(role: Role, path: string): boolean {
  const section = path.split('/')[1]
  if (['cameras', 'admin'].includes(section)) return role === 'admin'
  if (section === 'recognition') return role === 'admin' || role === 'operator'
  if (section === 'sessions') return role !== 'analyst'
  return true
}
export function mayOperate(role: Role) { return role === 'admin' || role === 'operator' }

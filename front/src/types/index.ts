export type RobotState =
  | 'OFFLINE'
  | 'IDLE'
  | 'RUNNING'
  | 'PICK'
  | 'PLACE'
  | 'E-STOP'
  | 'HOMING';

export type OperationMode = 'AUTO' | 'MANUAL';

export type LogType = 'ok' | 'warn' | 'err' | 'info' | 'cmd';

export interface LogEntry {
  id: number;
  time: string;
  msg: string;
  type: LogType;
}

export type CategoryKey = 'apple' | 'orange' | 'veggie';

export interface Category {
  key: CategoryKey;
  label: string;
  color: string;
  emoji: string;
}

export interface BeltItem {
  id: number;
  x: number;
  key: CategoryKey;
  label: string;
  color: string;
  emoji: string;
}

export interface UptimeSegment {
  type: 'work' | 'maintenance' | 'offline' | 'partial' | 'idle';
  label: string;
  color: string;
  start: string;
  end: string;
  hours: number;
  detail: string;
}

export interface OutputBin {
  label: string;
  color: string;
  fill: number;
  emoji: string;
}

export interface ConnectionInfo {
  host: string;
  protocol: string;
}

export interface SignalInfo {
  latency: string;
  packetLoss: string;
  strength: string;
}

export interface RobotParameters {
  convSpeed: number;
  armSpeed: number;
  pickHeight: number;
  sensitivity: number;
}

export type UptimeType = UptimeSegment['type'];

export interface UptimeTypeMeta {
  icon: string;
  label: string;
}

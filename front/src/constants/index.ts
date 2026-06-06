import type {
  Category,
  OutputBin,
  UptimeSegment,
  UptimeTypeMeta,
  ConnectionInfo,
} from '../types';

export const CATEGORIES: Category[] = [
  { key: 'apple', label: 'Apple', color: '#ef4444', emoji: '\u{1F34E}' },
  { key: 'orange', label: 'Orange', color: '#f97316', emoji: '\u{1F34A}' },
  { key: 'veggie', label: 'Vegetable', color: '#22c55e', emoji: '\u{1F966}' },
];

export const OUTPUT_BINS: OutputBin[] = [
  { label: 'Bin A \u2014 Apple', color: '#ef4444', fill: 72, emoji: '\u{1F34E}' },
  { label: 'Bin B \u2014 Orange', color: '#f97316', fill: 48, emoji: '\u{1F34A}' },
  { label: 'Bin C \u2014 Vegetable', color: '#22c55e', fill: 31, emoji: '\u{1F966}' },
];

export const CONNECTION_INFO: ConnectionInfo = {
  host: '192.168.1.42:8080',
  protocol: 'TCP/IP \u00B7 WebSocket',
};

export const UPTIME_SEGMENTS: UptimeSegment[] = [
  {
    type: 'work',
    label: 'Normal Work',
    color: '#22c55e',
    start: '06:00',
    end: '08:42',
    hours: 2.7,
    detail: 'Full auto-sort running. 1,842 items processed. Avg cycle 0.41s. Vision 98.2%.',
  },
  {
    type: 'maintenance',
    label: 'Maintenance',
    color: '#f59e0b',
    start: '08:42',
    end: '09:15',
    hours: 0.55,
    detail: 'Scheduled gripper calibration. End-effector cleaned. Belt tension checked.',
  },
  {
    type: 'work',
    label: 'Normal Work',
    color: '#22c55e',
    start: '09:15',
    end: '11:50',
    hours: 2.58,
    detail: 'Full auto-sort running. 2,104 items processed. Peak throughput 24 items/min.',
  },
  {
    type: 'offline',
    label: 'Server Off',
    color: '#ef4444',
    start: '11:50',
    end: '12:50',
    hours: 1.0,
    detail: 'Network outage. Robot halted. No data logged.',
  },
  {
    type: 'partial',
    label: 'Partial',
    color: '#f59e0b',
    start: '12:50',
    end: '15:50',
    hours: 3.0,
    detail: 'Backup server active. Manual override. Vision at 60% capacity.',
  },
  {
    type: 'work',
    label: 'Normal Work',
    color: '#22c55e',
    start: '15:50',
    end: '17:30',
    hours: 1.67,
    detail: 'Full systems restored. 1,593 items processed. All categories active.',
  },
  {
    type: 'idle',
    label: 'Idle',
    color: '#4b5563',
    start: '17:30',
    end: '18:00',
    hours: 0.5,
    detail: 'End of shift. Conveyor stopped. Robot in standby.',
  },
];

export const UPTIME_TYPE_META: Record<UptimeSegment['type'], UptimeTypeMeta> = {
  work: { icon: '\u25B6', label: 'Normal Work' },
  maintenance: { icon: '\u2699', label: 'Maintenance' },
  offline: { icon: '\u2715', label: 'Server Off' },
  partial: { icon: '\u25D1', label: 'Partial' },
  idle: { icon: '\u25CB', label: 'Idle' },
};

export const CAMERA_EXTERNAL_URL = '/snapshot';
export const CAMERA_ZED_URL = '';

export const TELEMETRY_MESSAGES: [string, 'info' | 'ok'][] = [
  ['Vision confidence: 97.8%', 'info'],
  ['Cycle time: 0.41 s', 'info'],
  ['Conveyor sync: OK', 'ok'],
  ['Camera: 60 fps', 'info'],
  ['Arm torque: 32%', 'info'],
];

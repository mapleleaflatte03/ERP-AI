import { bench, describe } from 'vitest';
import type { Document, DocumentStatus } from '../types';

const STATUSES: DocumentStatus[] = [
  'new', 'extracting', 'extracted', 'proposing', 'proposed',
  'pending_approval', 'approved', 'rejected', 'posted'
];

const documents: Document[] = Array.from({ length: 10000 }, (_, i) => ({
  id: `doc-${i}`,
  filename: `doc-${i}.pdf`,
  type: 'invoice',
  status: STATUSES[i % STATUSES.length],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}));

describe('Document Stats Calculation', () => {
  bench('Multiple Filters (Baseline)', () => {
    const pending = documents.filter(d => d.status === 'pending_approval').length;
    const approved = documents.filter(d => d.status === 'approved' || d.status === 'posted').length;
    const rejected = documents.filter(d => d.status === 'rejected').length;
    // prevent optimization
    if (pending < 0 || approved < 0 || rejected < 0) throw new Error();
  });

  bench('Single Pass Reduce (Optimized)', () => {
    const stats = documents.reduce(
      (acc, doc) => {
        if (doc.status === 'pending_approval') acc.pending++;
        else if (doc.status === 'approved' || doc.status === 'posted') acc.approved++;
        else if (doc.status === 'rejected') acc.rejected++;
        return acc;
      },
      { pending: 0, approved: 0, rejected: 0 }
    );
    // prevent optimization
    if (stats.pending < 0 || stats.approved < 0 || stats.rejected < 0) throw new Error();
  });
});

export const SCHEMA = {
  Arithmetic: [
    'TSD - Circular Tracks',
    'TSD - Boats & Streams',
    'TSD - Relative Speed',
    'Percentages - Successive Change',
    'Averages',
    'Ratio & Proportion',
    'Time & Work',
    'Simple & Compound Interest',
    'Profit & Loss',
    'Mixtures & Alligations',
  ],
  Algebra: [
    'Linear Equations',
    'Quadratic Equations',
    'Functions & Graphs',
    'Inequalities',
    'Logarithms',
    'Progressions (AP/GP)',
  ],
  Geometry: [
    'Circles',
    'Triangles',
    'Mensuration - 3D',
    'Coordinate Geometry',
    'Polygons',
  ],
  'Number System': [
    'LCM & HCF',
    'Divisibility Rules',
    'Remainders & Cyclicity',
    'Factors & Multiples',
  ],
  'Modern Math': [
    'Permutation & Combination',
    'Probability',
    'Set Theory',
    'Data Sufficiency',
  ],
  'Data Interpretation': [
    'Tables',
    'Bar Graphs',
    'Line Graphs',
    'Caselets',
    'Pie Charts',
  ],
  Verbal: [
    'Reading Comprehension',
    'Para Jumbles',
    'Critical Reasoning',
    'Vocabulary',
  ],
}

export const TOPICS = Object.keys(SCHEMA)

export const STATUSES = ['Correct', 'Incorrect', 'Skipped']

export const ERROR_TYPES = ['Conceptual', 'Calculation', 'Misread', 'Silly Mistake']

export const MASTER_SCHEMA_ROW_COUNT = 40

export function blankRow(qno) {
  return {
    id: `r-${qno}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    qno,
    topic: '',
    pattern: '',
    status: '',
    errorType: '',
    note: '',
  }
}

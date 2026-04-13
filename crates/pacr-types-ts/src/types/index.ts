// src/types/index.ts
// Barrel export — the public API surface of the type system

// Identity space
export type {
  AgentId,
  EventId,
  CapabilityRef,
  EventIdStructure,
  AevumId,
} from './identity.js';
export { isAgentId, isEventId, extractOrigin } from './identity.js';

// PACR six-tuple
export type {
  ConfidenceInterval,
  LandauerUnit,
  Joules,
  Seconds,
  Bytes,
  BitsPerSymbol,
  LandauerCost,
  CausalPredecessorSet,
  ResourceConstraintTriple,
  CognitiveSplit,
  OpaquePayload,
  PACRecord,
} from './pacr.js';
export { isPACRLite } from './pacr.js';

// AgentCard
export type {
  Capability,
  AgentCardMetadata,
  AgentCard,
  AgentBehaviorEntropy,
  AgentInteractionSummary,
  InteractionEdge,
} from './agent-card.js';

// Envelope
export type {
  EnvelopePrimaryHeader,
  EnvelopePACRExtension,
  Envelope,
} from './envelope.js';

// Commensuration
export type {
  CommensuationContext,
  CommensuationLayer,
} from './commensuration.js';
export {
  BOLTZMANN_CONSTANT,
  LN2,
  PLANCK_CONSTANT,
  REDUCED_PLANCK_CONSTANT,
  SPEED_OF_LIGHT,
  LANDAUER_UNIT_AT_300K,
} from './commensuration.js';

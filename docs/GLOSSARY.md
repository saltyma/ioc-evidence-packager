# Glossary

## Indicator of compromise (IOC)

An observable value that may be associated with malicious activity, such as an IP address, domain, URL, or file hash. It is a lead requiring context, not an automatic verdict.

## Observable

A value that can be seen or measured in security data. An observable becomes useful as an IOC when intelligence or investigation context associates it with suspicious activity.

## Direct match

An event whose compatible structured field normalizes to the queried IOC. The field path, original value, normalized value, and matching rule are recorded.

## Context event

An event that does not contain the IOC but is included by an explicit correlation rule, such as sharing the same host and process within a configured time window.

## Correlation

Connecting events or entities using declared relationships such as shared host, user, process, file, or time proximity. Correlation suggests relevance; it does not prove causation.

## Provenance

Information showing where an evidence item came from: source file, file hash, adapter/version, source record or line, and original value.

## Integrity hash

A cryptographic digest used to detect whether bytes changed. This project uses SHA-256 for input/output integrity. A matching hash does not prove who created or acquired the file.

## Evidence package

The generated set of human- and machine-readable artifacts: report, normalized evidence, source inventory, and manifest.

## Manifest

A machine-readable record of tool/schema versions, parameters, input/output hashes, counts, warnings, and matching policy used to generate a package.

## Source inventory

A list of input files and their sizes, hashes, adapters, accepted records, rejected records, and processing errors.

## Normalization

Conversion to a comparable representation, such as lowercasing a hash or canonicalizing an IP, while preserving the original value.

## Canonical event

The project's vendor-neutral representation of a source record, including time, entities, observables, provenance, raw data/reference, and warnings.

## Adapter

A versioned parser/mapper that converts one input format or vendor schema into canonical events.

## SIEM

Security information and event management: a platform for centralizing, searching, correlating, and alerting on security telemetry.

## EDR

Endpoint detection and response: technology that collects endpoint telemetry and supports detection, investigation, and response.

## SOC

Security operations center: the people and processes that monitor, triage, investigate, and respond to security events.

## DFIR

Digital forensics and incident response: acquisition, examination, analysis, and communication of digital evidence during investigations.

## Threat intelligence enrichment

Adding external or internal context to an observable, such as reputation, registration, malware relationships, or prior sightings. It is separate from finding occurrences in local logs.

## Chain of custody

Documentation and controls that track evidence possession and handling over time. File hashes and provenance support integrity, but this tool alone cannot establish a complete legal chain of custody.

## Deterministic output

Output whose evidence content and ordering remain equivalent when inputs, settings, and tool versions are equivalent.

# References

Official standards, guidance, datasets, and product documentation used for the product and architecture study. Reviewed 2026-08-06. APIs, terms, rate limits, schemas, and product capabilities change; re-check the linked primary sources before implementation and release.

## Incident response and evidence handling

- [CISA — Federal Government Cybersecurity Incident and Vulnerability Response Playbooks](https://www.cisa.gov/sites/default/files/2023-01/federal_government_cybersecurity_incident_and_vulnerability_response_playbooks_508c_5.pdf) — indicator documentation, analysis, and response-team communication.
- [NIST SP 800-86 — Guide to Integrating Forensic Techniques into Incident Response](https://csrc.nist.gov/pubs/sp/800/86/final) — forensic process and use of multiple data sources/logs.
- [NIST SP 800-61 Rev. 3 — Incident Response Recommendations and Considerations for Cybersecurity Risk Management](https://csrc.nist.gov/pubs/sp/800/61/r3/final) — current NIST incident-response guidance context.

## Data models and normalization

- [OASIS STIX 2.1 specification](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html) — cyber-observable data, Observed Data, Indicators, Sightings, relationships, and versioning.
- [MITRE ATT&CK data and tools](https://attack.mitre.org/resources/attack-data-and-tools/) — official ATT&CK STIX data access and usage guidance.
- [Elastic Common Schema reference](https://www.elastic.co/docs/reference/ecs) — vendor-neutral security/event field conventions.
- [Open Cybersecurity Schema Framework](https://ocsf.io/) — open cybersecurity event schema and ecosystem.
- [Public Suffix List](https://publicsuffix.org/list/) — registrable-domain boundary data and usage.
- [RDAP information](https://about.rdap.org/) and [ICANN RDAP](https://www.icann.org/rdap) — registration-data protocol and bootstrap context.

## Desktop and local data technology

- [Qt for Python / PySide6 documentation](https://doc.qt.io/qtforpython-6/) — official Python bindings and Qt desktop application guidance.
- [SQLite JSON functions](https://www.sqlite.org/json1.html) — JSON storage/query capabilities.
- [SQLite FTS5 extension](https://www.sqlite.org/fts5.html) — optional full-text indexing capabilities and behavior.
- [DuckDB data import overview](https://duckdb.org/docs/stable/data/overview) — local CSV, JSON, Parquet, and query options for later large-source scanning.
- [Jinja documentation](https://jinja.palletsprojects.com/) — report templates and auto-escaping behavior.

## Evidence and timeline input tools

- [Wazuh server API reference](https://documentation.wazuh.com/current/user-manual/api/reference.html) — Wazuh API capabilities.
- [Wazuh indexer indices](https://documentation.wazuh.com/current/user-manual/wazuh-indexer/wazuh-indexer-indices.html) — documented index structures and access considerations.
- [Suricata EVE JSON output](https://docs.suricata.io/en/latest/output/eve/eve-json-output.html) — network event JSON structure.
- [Zeek log formats and log files](https://docs.zeek.org/en/current/script-reference/log-files.html) — Zeek structured log sources.
- [Hayabusa repository](https://github.com/Yamato-Security/hayabusa) — Windows event log triage and JSONL/CSV timeline outputs.
- [Chainsaw repository](https://github.com/WithSecureLabs/chainsaw) — Windows forensic artifact search and detection.
- [Plaso output and formatting](https://plaso.readthedocs.io/en/latest/sources/user/Output-and-formatting.html) — timeline export behavior and formats.
- [Sigma documentation](https://sigmahq.io/docs/) — portable detection-rule concepts used by adjacent tools.

## Enrichment providers and datasets

- [CIRCL hashlookup](https://www.circl.lu/services/hashlookup/) — online and offline known-file hash lookup options.
- [ThreatFox API](https://threatfox.abuse.ch/api/) — IOC query/submission capabilities and authentication guidance.
- [URLhaus API](https://urlhaus.abuse.ch/api/) — malicious URL/payload metadata API.
- [MalwareBazaar API](https://bazaar.abuse.ch/api/) — malware sample metadata API; the project does not automatically download samples.
- [GreyNoise Community API](https://docs.greynoise.io/reference/getcommunityip) — limited community IP context.
- [AbuseIPDB API](https://www.abuseipdb.com/api.html) — reported IP-abuse context and usage documentation.
- [VirusTotal public vs. premium API](https://docs.virustotal.com/reference/public-vs-premium-api) — public API quotas and usage restrictions that require explicit BYOK/product decisions.
- [VirusTotal API v3 overview](https://docs.virustotal.com/reference/overview) — official object-oriented API and public/premium boundary used by the optional connector.
- [VirusTotal IP address report](https://docs.virustotal.com/reference/ip-info) and [file report](https://docs.virustotal.com/reference/file-info) — official existing-object `GET` endpoints; the project does not upload samples.

## Intelligence, case, and timeline platforms

- [MISP features](https://www.misp-project.org/features/) — intelligence model, correlations, sharing, reports, APIs, and exports.
- [PyMISP repository](https://github.com/MISP/PyMISP) — official Python library for MISP automation.
- [OpenCTI documentation](https://docs.opencti.io/latest/) — knowledge graph, cases, feeds, connectors, and platform architecture.
- [OpenCTI integrations](https://docs.opencti.io/latest/deployment/integrations/) and [connectors](https://docs.opencti.io/latest/deployment/connectors/) — connector and integration models.
- [VirusTotal Graph documentation](https://docs.virustotal.com/docs/graph-documentation) — pivots and relationships in VirusTotal data.
- [IntelOwl documentation](https://intelowlproject.github.io/docs/IntelOwl/introduction/) — analyzer/connector orchestration and observable enrichment.
- [Timesketch project](https://timesketch.org/) and [API client](https://timesketch.org/developers/api-client/) — forensic timeline workflow and integration surface.
- [Velociraptor documentation](https://docs.velociraptor.app/docs/) and [server API](https://docs.velociraptor.app/docs/server_automation/server_api/) — endpoint collection/analysis and the power/risk of automation.
- [TheHive API documentation](https://docs.strangebee.com/thehive/api-docs/) — case/alert/observable integration surface.

## Interpretation notes

The problem study distinguishes a product's documented center of gravity from whether a capability can be created through configuration, extensions, queries, or custom development. A relative gap is not a claim of product incapability.

The product-positioning chart is an author inference based on documented scope and deployment models. It is not a benchmark, vendor ranking, or market-share analysis.

Provider entries are candidates, not endorsements. Implementation must verify authentication, quotas, terms, privacy, redistribution rights, schema stability, and commercial-use constraints at that time.

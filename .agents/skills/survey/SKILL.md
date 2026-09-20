---
name: survey
description: Conduct an interactive, read-only market survey or broad comparison requiring market coverage and application-specific selection. Define the function, map meaningful solution families, assess fit, compare evidence and acquisition tradeoffs, and retain a quick direction check before broad research. Do not use for a bounded question that a more specific survey-* skill can answer directly.
---

# Survey

Conduct an educational market survey rather than merely naming a winner. Use
the category, application, candidates, constraints, and preferences supplied by
the user and current conversation. Treat named products as seeds, not
presumptive winners.

An explicit request to survey a category normally qualifies when it requires
both market coverage and application-specific selection. A bounded comparison
of a few known products does not qualify when a companion skill can answer it
directly.

Do not purchase anything, contact a vendor, create an account, or modify files
unless the user separately requests that action.

## Compose The Survey

For a full survey, use applicable independently useful `survey-*` skills when
they are available:

- use `survey-market-map` to discover mechanisms, product families,
  manufacturers, regions, and market channels;
- use `survey-application-fit` when a device, environment, interface, workflow,
  or exact application affects compatibility;
- use a category specialist, such as `survey-hand-tools`, for category-specific
  taxonomy, comparison dimensions, sources, traps, and validation methods.

Specialists augment this workflow; their absence must not prevent a survey of
an otherwise researchable category. Give every contributor the same research
brief and require structured findings that can be reconciled with the
candidate ledger.

## Build The Research Brief

Resolve these fields from the request and existing context:

1. **General function:** the outcome required, without assuming a product
   style.
2. **Specific application:** the device, environment, workflow, frequency, and
   consequences of poor performance.
3. **Compatibility references:** relevant models, parts, interfaces,
   standards, diagrams, measurements, consumables, and adjacent products.
4. **Seed solutions:** supplied or initially discovered products and the role
   each appears to fill.
5. **Preferences and constraints:** quality, service, budget, availability,
   location, ergonomics, origin, ecosystem, and longevity.
6. **Eligibility rule:** a short test every included solution must pass.
7. **Exclusion rule:** nearby categories that do not perform the required
   function.

Read applicable local documentation before relying on external assumptions.
Ask only for missing information that could materially change the scope,
comparison groups, or recommendation.

## Perform The Direction Check

Before broad research:

1. Find two to four diverse preliminary mechanisms or solutions.
2. Confirm provisionally that each passes the eligibility rule and could suit
   the application.
3. Show the brief, preliminary families, and important interpretation choices.
4. Ask whether the direction and scope are correct, then pause.

Skip the pause only when the user requests uninterrupted research or has
already confirmed the same brief and direction in the current conversation.
Do not impose this pause on narrow questions handled by a standalone companion
skill.

## Maintain The Candidate Ledger

Track every materially distinct eligible mechanism, family, and serious
candidate discovered by any researcher. Record enough to classify each in the
final result as:

- a comparison candidate;
- an adjacent alternative or complement; or
- an explicit exclusion with a reason.

Use product findings to discover manufacturers and manufacturer findings to
discover products. Do not silently drop a meaningful family because it is
expensive, weakly documented, or unlikely to win.

For substantial surveys, divide independent regions, channels, manufacturers,
or evidence questions among parallel researchers when that improves coverage.
Give each researcher the same function, eligibility rule, application context,
evidence vocabulary, and requested output shape. Reconcile every returned
candidate through the shared ledger.

## Apply Evidence Discipline

Prefer, when practical:

1. Manufacturer product pages, manuals, catalogs, drawings, and support terms.
2. Authorized distributors and established specialist retailers.
3. Independent demonstrations, technical reviews, and application reports.
4. Detailed forums and owner reports.
5. Search snippets and marketplace listings only as discovery leads.

This preference order governs support for claims, not where candidates may be
discovered. Use detailed community discussions and owner reports to discover
less-visible options and investigate application-specific behavior,
limitations, failures, and long-term experience; corroborate consequential
claims when practical.

Verify consequential claims at their source. Record URLs and the observation
date for current price, availability, and lifecycle claims. Present conflicts
rather than silently choosing one source.

Use these claim states consistently:

- **Documented:** stated by a primary or authoritative source.
- **Corroborated:** supported by multiple credible independent sources.
- **Inferred:** reasoned from design, images, wording, or adjacent evidence.
- **Unknown:** absent or contradictory evidence.

Do not infer product origin from company headquarters. Similar appearance,
specifications, packaging, or language may justify investigating a relationship
but does not prove common design, manufacture, ownership, or private labeling.

## Form Comparable Groups

Group solutions first by function and mechanism. Then separate them when
differences materially affect capability, compatibility, access, workflow,
performance, serviceability, safety, required complements, or ownership cost.
Keep adjacent but non-equivalent solutions visible instead of forcing them into
one ranking.

Adjust comparison dimensions to the category. Distinguish product-specific
evidence from brand reputation and application match from general quality.
For each serious candidate, collect the category-appropriate subset of exact
function and mechanism, configurations and capacity, materials and
construction, performance, ergonomics and access, serviceability and
consumables, product-specific origin, warranty and service path, lifecycle and
availability, price and package contents, and credible application reports.

Normalize commercial comparisons. Identify MSRP versus current street price,
stock status, single products versus sets, included accessories, shipping,
duties, consumables, and complementary products when material. State the date
of price and availability observations.

## Resolve Uncertainty

For every unanswered question that could change the choice, recommend the
least costly reliable validation: locate a manual or drawing, take a
measurement, check a compatibility reference, find an exact-application
report, ask a narrow manufacturer question, or conduct a controlled physical
test. Never imply that contact, measurement, purchase, or testing occurred.

## Present The Result

Lead with useful conclusions, then provide enough structure for the user to
make a different tradeoff. Include as appropriate:

- the resolved function, eligibility rule, and application constraints;
- the meaningful mechanisms and product families;
- manufacturer and channel coverage;
- tables containing only genuinely comparable products;
- normalized price and availability context;
- strengths, limitations, evidence quality, and fit confidence;
- conditional recommendations for different priorities;
- important unknowns and next validation steps; and
- notable exclusions whose absence would otherwise be surprising.

Distinguish best made, best matched, best supported, and best value when they
are different. Reconcile the candidate ledger before presenting the result.

## Stop Broad Discovery

Stop when the relevant mechanisms are represented, important regions and
channels have been checked, each serious comparison group has reasonable
coverage or an explained gap, additional searches no longer change the
groupings or likely guidance, and consequential unknowns have become explicit
validation steps. Do not stop merely because one compelling product was found,
and do not continue solely to lengthen the candidate list.

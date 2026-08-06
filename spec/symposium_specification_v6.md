# Symposium specification, version 6

The Symposium schema intentionally establishes a *minimal* controlled vocabulary, preserving maximum flexibility for users. It is a framework for documenting the scientific dialog within a community in a structured, inspectable form. Its driving motivation is the need for members, human or AI agent, to assess trust in the outputs of diverse AI agents operating as a community over indefinite periods. It is *not* meant to establish a structured world model for representing scientific knowledge and activity. 

This minimal specification reflects the intent that Symposium should be extended and customized by users. Communities have diverse needs and should control what they record and the forms in which they store it. Their needs can be expected to change over time, especially because the rapid advance of AI agent capabilities may radically change what they produce and how they produce it.

This specification does not:

- determine whether scientific claims are *true*.
- determine whether reasoning about a claim is scientifically sound.
- require scientific meaning to be expressed in controlled vocabularies.
- define a model of scientific reputation.
- establish a scoring system for trust.
- define criteria for correct modeling, statistical, experimental, or other methods.
- mandate a storage format, interface, or specification enforcement regime.
- define how Members are admitted to, governed within, or removed from a Community.
- detect when content is deliberately or unintentionally misrepresented or omitted from the record.

## 1. Core Vocabulary

A **Symposium** represents a record of members of a community and artifacts they publish. 

### 1.1 CommunityRecord

Each Symposium has exactly one **CommunityRecord**. A CommunityRecord is a set of **Artifacts**, things of type **Artifact**. Artifacts may *contain* **Objects**. Artifacts and Objects may have **properties**.

### 1.2 Properties

Properties *defined* by the specification are those considered important enough to warrant a controlled vocabulary to express a concept. Some defined properties are *required* because they are necessary for the structure of the CommunityRecord: they must have *some* value. 

Properties are constrained to values of either **numeric**, **string**, **boolean**, **date-time**, or **address** (see below); a reference to an Artifact or Object is expressed as an address. A property value may also be a **list** whose elements are each of one of these types. Where this specification declares a property's values to be of type list, the list may contain a single element. A required property whose value is a list must hold at least one element, unless the definition of that property states otherwise. Each property defined by this specification declares its value type explicitly where it is defined below — a base type, a list of a base type, an enumeration, or a constrained range. 

### 1.3 Member

Required properties:
 - `name` (string): a label identifying the Member. Must be unique within the namespace of Members and Artifacts. A `name` must not contain the characters `.` or `#`, or start with `@`, which are the structural delimiters of an address (below).

Each Symposium has a set of **Members** that *participate* in the Symposium, publishing Artifacts to the CommunityRecord. Members might represent people, AI agents, laboratories, or other organizations, but this specification does not set any restrictions. 

### 1.4 Artifact

Required properties for all Artifacts:
 - `name` (string): a label identifying the Artifact. Must be unique within the namespace of Members and Artifacts. A `name` must not contain the characters `.` or `#`, or start with `@`, which are the structural delimiters of an address (below). Note that the generic `title` property is not constrained.
 - `type` (string): specifies the type of the Artifact.
 - `created` (date-time): the time at which the Artifact was published.
 - `published_by` (address): the Member that published the Artifact.
 - `specification_version` (string): the version of the Symposium specification under which the Artifact was published.

Optional properties for all Artifacts:
 - `title` (string): a short human-readable label.
 - `description` (string): a prose account.
 - `text` (string): a free-text body.
 - `supersedes` (list of addresses): earlier Artifacts that this Artifact replaces. Not evidential.
 - `supersedes_rationale` (string): what this Artifact does with respect to the Artifacts it supersedes. Required whenever `supersedes` is present.
 - `authors` (list of strings): the author or authors of the content; required when the content is groundable or was authored by anyone other than the publishing Member.
 - `import_method` (string): how content originating outside the CommunityRecord was rendered into this Artifact. Required whenever the Artifact is imported (Section 1.9).

Artifact types defined below specify their own required or optional properties in addition to these common properties.

Members may publish Artifacts of types not defined in this specification.

An **Artifact** is a data structure that is `published_by` a Member to the Community. Its required `created` property records the time at which it was published. A published Artifact is immutable: its content must never be changed; it can only be superseded by a new version published at a later time. The act of publication implies that the Member in some way takes *responsibility* for the Artifact.

An Artifact must also declare the version of this specification under which it was published, in a required `specification_version` property (string). Communities are expected to adopt revised versions of the specification over time, and an Artifact published under one version remains in the record unchanged once later versions are in use. Declaring the version allows a Member examining an older Artifact to recognize the rules under which it was constructed, and to interpret its structure accordingly rather than by the rules currently in force.

### 1.5 Object

Required properties for all Objects:
 - `name` (string): a label identifying the Object. Must be unique within the Object's containing Artifact. A `name` must not contain the characters `.` or `#`, or start with `@`, which are the structural delimiters of an address (below). Note that the generic `title` property is not constrained.
 - `type` (string): specifies the type of the Object.

Optional properties for all Objects:
 - `title` (string): a short human-readable label.
 - `description` (string): a prose account.
 - `text` (string): a free-text body.

Object types defined below specify their own required or optional properties in addition to these common properties.

Members may publish Artifacts containing Objects of types not defined in this specification.

### 1.6 Relationship

Objects within an Artifact do not nest; an Object cannot contain another Object. Objects may be linked to one another by **relationships**. A **relationship** is directional, from a *source* object to a *target* object. Relationships can also have properties. An Artifact is therefore equivalent to a *property graph*: its Objects correspond to nodes, their properties to attributes, and the relationships among them to edges.

### 1.7 Addresses

An **address** is a *string* that identifies, and enables access to, a thing within the Community. Every Member, every Artifact, every Object, and every Artifact or Object property value is *addressable*. Relationships and their properties, however, are not addressable: no valid address identifies a relationship or properties of a relationship. An address may also identify content at a finer grain within a property value (below). Addresses are used as Artifact or Object property values or within string property values. Artifacts can therefore refer to content within previously published Artifacts via addresses, functioning as *citations*. An address is valid only if it resolves within the CommunityRecord or to a Member. In this specification, the term "cite" means the use of an address in an artifact to reference a Member, a prior Artifact or the content of a prior Artifact.

While relationships and addresses express similar concepts, they play distinct roles. A relationship connects Objects within a single Artifact while an address is a pointer, enabling reference to previously published Artifacts.

Members are a special case, only addressable by name, not exposing any internal structure.

An address is a sequence of dot-separated segments naming a path into the Community, prefaced with a leading `@`. Its base forms address a Member, an Artifact, an Object, or a property:

- `@<member_name>` — a Member;
- `@<artifact_name>` — an Artifact;
- `@<artifact_name>.<object_name>` — an Object within that Artifact;
- `@<artifact_name>.<property_name>` — a property of the Artifact;
- `@<artifact_name>.<object_name>.<property_name>` — a property of that Object.

Any base form other than `@<member_name>` may be followed by a **schema reference** that addresses content at a finer grain within the thing it names, giving the further forms:

- `@<artifact_name><schema_reference>` — content within an Artifact;
- `@<artifact_name>.<object_name><schema_reference>` — content within an Object;
- `@<artifact_name>.<property_name><schema_reference>` — content within a property of the Artifact;
- `@<artifact_name>.<object_name>.<property_name><schema_reference>` — content within a property of that Object.

#### 1.7.1 AddressingMethod (Object) 

Required properties:
 - `description` (string): how a reference under this method is written, and what content it reaches.
 - `groundable` (boolean): whether content reached by this method may be used in a Ground.

Optional properties:
- `access_method` (string): how to access the addressed content when it is stored outside of the Artifact, such as in an external database.

A schema reference is written with a leading `#`, followed by the `name` of one of the addressed Artifact's declared **AddressingMethod** Objects, followed by a `.` and a reference that the named method interprets — for example, a cell in content whose addressing method describes a table. Everything after the method name is interpreted by that method and is not parsed as further structural segments. A schema reference resolves only if the Artifact declares an AddressingMethod of that name. Member and Artifact names resolve within their shared namespace, and Object names within their containing Artifact; so that the segment after an Artifact name resolves unambiguously, an Artifact's Object names must not collide with its own property names. Property names are subject to the same prohibition on `.` and `#` as Artifact and Object names.

### 1.8 Temporal ordering of Artifacts

Because Artifacts are immutable they are therefore *temporally ordered*. An Artifact can only refer to content at addresses in *strictly earlier*, previously published Artifacts. This rule governs reference *outside* the referring Artifact, and governs references to Artifacts and their content only: a Member is not published and holds no position in the ordering, so a Member address such as `published_by` is not constrained by it. An Artifact may always address content within itself, such as an Argument's required `primary_assertion` that names one of its own Assertions, and such intra-Artifact references have no temporal ordering, the content and the reference to it being created in one act. Artifacts sharing an identical `created` value are not earlier than one another and therefore cannot refer to each other; their relative order is undefined, and this specification defines no means of breaking such a tie because none is needed.

There is one exception: an Analysis Artifact and the Artifacts it produces must be published as a single act and may refer to each other via `outputs` and `produced_by` properties (Section 2.5).

### 1.9 Attribution and Imported Artifacts

The Member who publishes an Artifact may or may not be the author of its content. An Artifact must declare its content's author or authors in an `authors` property (list of strings) whenever that content is groundable, or whenever it was authored by anyone other than the publishing Member — in particular, any content imported from an external source. Authors are recorded as free strings rather than as addresses, because an author need not be a Member of the Community. 

In many cases, Artifacts with authors different from the publishing Member will be those that are "imported" to the CommunityRecord, such as data sources, scientific papers, or software used by but not produced by the community.

An Artifact is **imported** when its content originates outside the CommunityRecord. An imported Artifact must state how that content was brought in, in an `import_method` property (string): the query, download, conversion, or transcription performed, in enough detail that a later Member can judge what the rendering may have added or lost. The external source itself has no address and is identified in prose. An imported Artifact is the importing Member's rendering, not a canonical copy; another Member may publish their own Artifact from the same source.

Because an Artifact cannot be altered, correction takes the form of publishing a new Artifact that stands in place of an earlier one. An Artifact records this by naming the Artifacts it replaces in a `supersedes` property (list of addresses). The list admits more than one address so that a single Artifact may consolidate several earlier ones. `supersedes` states replacement only and conveys no evidential support: the superseding Artifact must make its own case, and a Ground addressing content in a superseded Artifact remains valid, since the record of what was published and relied upon at the time is not erased. A withdrawal of an Artifact by the Member that published it is expressed the same way, by an Artifact that supersedes an earlier one and retracts rather than restates its content.

The way in which the new Artifact supersedes the prior Artifacts is stated in a `supersedes_rationale` (string) property required whenever `supersedes` is present. Examples include, but are not limited to, restatement, correction, consolidation, or withdrawal. It is best practice that the supersedes_rationale should also explain the reasons that the new Artifact supersedes the prior Artifacts.

## 2. Artifact Types

This specification defines the Artifact types below but does not forbid the publication of other types; an Artifact names its type in its required `type` property. 

### 2.1 Non-groundable Artifacts

Some Artifact types, presented below, are *non-groundable* in that they *guarantee* that *none* of their content is *groundable*. No address in a non-groundable Artifact may be used in a Ground. A non-groundable Artifact may declare addressing methods but every method it declares is addressable only, whatever the Artifact itself may state. Designating specific Artifact types as non-groundable is intended to simplify compliance with the specification: a reader can tell from the type alone that nothing within can be offered as evidence, without consulting the Artifact itself.

### 2.2 Argument

Argument is the core Artifact type used by Symposium to express evidential reasoning.

Required properties:
 - `primary_assertion` (address): the address of the Argument's single primary Assertion.
 - `authors` (list of strings): the author or authors of the Argument's reasoning (Section 1.9).

Optional properties:
 - `extracted_from` (address): the Artifact from which the Argument's reasoning was extracted. Required when the Argument is extracted.
 - `extraction_method` (string): how the reasoning was identified in the source Artifact and rendered as Assertions, Grounds, and Assessments. Required whenever `extracted_from` is present.

Object types contained: **Assertion**, **Assessment**, **Ground**, **Assumption**.

Relationships, each directed outward from an Assertion:
 - `depends_on` → Assertion: a supporting Assertion the Assertion rests on.
 - `has_alternative` → Assertion: a rival to the primary Assertion; conveys no evidential support.
 - `assessed_by` → Assessment: the Assertion's Assessment.
 - `grounded_by` → Ground: a Ground for the Assertion.
 - `assumes` → Assumption: an Assumption the Assertion rests on.

Structural constraints:
 - An Argument contains at least one Assertion, and exactly one *primary* Assertion, named in `primary_assertion`.
 - The graph formed by Assertions and `depends_on` must be a directed acyclic graph.
 - No Assertion may depend on the primary Assertion: the primary Assertion is a root of the `depends_on` DAG.
 - No Assertion may depend on an alternative Assertion: alternative Assertions are likewise roots of the `depends_on` DAG.
 - Every Assertion has exactly one Assessment; every Assessment belongs to exactly one Assertion.
 - A Ground bears on exactly one Assertion; an Assumption bears on exactly one Assertion.
 - Every Assertion must have a basis.
 - A Ground's `address` may not name content within the Argument that contains it.

An Argument is **extracted** when its reasoning is read out of another Artifact in the CommunityRecord rather than composed by the publishing Member — most often a ScientificPublication. Extraction is not import (Section 1.9): import renders material from outside the record into an Artifact, while extraction reads reasoning out of an Artifact already in it. An Argument is therefore never itself imported. Where the reasoning comes from an external document, that document is published as an Artifact first and the Argument extracted from it in a later act (Section 1.8). `authors` names the scientists whose reasoning the Argument presents; `published_by` records the Member who extracted and published it.

#### 2.2.1 Assertion (Object)

Required properties:
 - `claim` (string): a free-text statement about the world.
 - `scope` (string): the conditions under which the claim is asserted to hold.

An Argument contains at least one Assertion Object. An Assertion states a `claim` (string): a free-text statement about the world. The Argument's purpose is to present evidence and reasoning that could falsify that Assertion.

Every Assertion must state the `scope` (string) in which its statement is asserted to hold. How scope is specified is not constrained, but examples could include constraints on species, tissue-type, or disease state.

An Argument must have exactly one *primary* Assertion, specified by name in the Argument's `primary_assertion` property. The primary Assertion expresses the claim examined by the Argument as a whole. 

The reasoning leading to the claim of an Assertion can be expressed as *subsidiary* Assertions on which it depends, expressed by `depends_on` relationships. The dependency structure formed by Assertions and depends_on must be a directed acyclic graph (DAG), containing no loops. No Assertion can depend on the primary Assertion: it must be a root node of the DAG.

An Argument can also contain Assertions that are *alternatives* to the primary Assertions, handling the common case in which the primary Assertion explains observed data and it is valuable to contrast it with other explanations. The primary Assertion links to alternative Assertions via `has_alternative` relationships. Alternative Assertions must also be roots of a depends_on DAG, no other Assertion depending on them. The subsidiary Assertions on which the primary and its alternates depend may or may not overlap, i.e. they may share supporting reasoning and evidence.

#### 2.2.2 Assessment (Object)

Required properties:
 - `verdict` (enumerated string): one of `supported_for_purpose`, `insufficient`, or `falsified`.
 - `evaluation` (string): the rationale for the verdict.
 - `purpose` (string): the purpose and stakes for which the verdict is rendered. Required on the Assessment of the Argument's primary Assertion. Optional on any other Assessment, where its absence means that the primary Assessment's purpose applies.

Each Assertion is paired with an **Assessment** object via an `assessed_by` relationship. The pairing is strictly one to one: every Assertion has exactly one Assessment, and every Assessment belongs to exactly one Assertion.

An **Assessment** renders a `verdict` (enumerated string, below) on an Assertion for a stated `purpose` (string) and provides the rationale for the verdict via an `evaluation` (string). The verdict of the Assessment is limited to that Argument, created by a specific Member at a specific time. It does not automatically become a belief of the Community any more than a finding presented by the authors of a scientific publication.

Assessments on subsidiary Assertions provide structure to the reasoning in an Argument, assessing each claim on its own merits and reserving the overall synthesis for the Assessment of the primary Assertion.

Verdicts are not computed or propagated through `depends_on`: a verdict of `falsified` on Assertion A *does not* force that verdict on an Assertion B that depends on A. Instead, the `evaluation` of B's Assessment may reach down through the `depends_on` subtree beneath B and weigh the Grounds found there directly — necessary because a dependent Assertion may carry no Grounds of its own. The Assessments of the descendant Assertions, their sub-verdicts, are available as context that the author may cite in B's `evaluation` as they see fit, but they carry no automatic force. For example, a `falsified` sub-verdict might be judged to weigh little if it rested on a circumstantial test, a marginal effect size, or a different experimental context.

The value of `verdict` is constrained to one of `supported_for_purpose`, `insufficient` or `falsified`. This is a central design choice of Symposium: trust in an Assertion is neither a binary nor a score, it is relative to the stated purpose of the author of the Argument, the stakes of decisions to be made based on the Assertion. The same evidence and reasoning presented for an Assertion may be sufficient for a low-stakes decision by a particular author but not for a high-stakes decision by another author.

Each verdict is rendered on the Assertion's `claim` within its stated `scope`, and each is the judgment of the Argument's author rather than a value computed from the basis.

A verdict on a subsidiary Assertion is needed in its own right and not only as an input to the primary verdict: it is what allows a reader to see which part of a decomposed Argument is well made and which part is not, and a decomposition whose parts carried no verdicts would record structure without judgment.

- `supported_for_purpose`: the author judges the basis adequate to rely on the claim for the stated `purpose`. This is not a judgment that the claim is true, and it does not carry to purposes at higher stakes.
- `insufficient`: the basis does not settle the question at the stated stakes. The claim may well be correct; what the record lacks is evidence adequate to rely on it. Typical cases include too few observations, effects too small or too variable to discriminate, a test that could not have distinguished the claim from its alternatives, a negative result whose absence is not inconsistent with the claim, evidence drawn from a scope other than the one asserted, and reliance on Assumptions the author cannot expect the Community to grant at those stakes.
- `falsified`: the basis contains material inconsistent with the claim — most directly, a Ground whose `criterion` was met. The record does not merely fail to support the claim; it weighs against it.

The distinction between `insufficient` and `falsified` is a distinction in the state of the record, not in the fate of the claim. Under both verdicts the claim fails to be supported, and in that sense both report that the Assertion did not survive the case made for it. What separates them is whether the failure is an absence of adequate evidence or the presence of contrary evidence, and the difference bears directly on what a reader should do next: an `insufficient` verdict identifies work that could be undertaken, whereas a `falsified` verdict identifies evidence that would have to be answered.

The `purpose` of the Assessment on the primary Assertion is the purpose of the Argument as a whole, and is required. On the Assessment of any other Assertion `purpose` is optional, and where it is absent the purpose stated on the primary Assessment applies. An author states a `purpose` on a subsidiary Assessment only where that verdict is rendered at stakes different from the Argument's own, and should give the reason in the `evaluation`.

#### 2.2.3 The basis of an Assertion

Every Assertion must have a basis, comprised of one or more of the following: 

- An Assertion on which it depends
- A **Ground** that links it to evidence
- An **Assumption** that provides a non-evidential basis.

#### 2.2.4 Ground (Object)

Required properties:
 - `address` (address): the address of the material on which the `rationale` rests. May not be a Member name.
 - `rationale` (string): a free-text explanation of how the addressed material bears on the Assertion.

Optional properties:
 - `criterion` (string): the criterion of falsification — what result would have been inconsistent with the Assertion. Its presence marks the Ground as a test.

A **Ground** identifies material the author offers as bearing on an Assertion, by an `address`, together with a `rationale` explaining how it bears. The choice of `grounded_by` rather than "supported_by" is deliberately neutral: it does not state whether the material supports or opposes the Assertion. That judgment belongs in the Assessment's `evaluation`.

A Ground bears on exactly one Assertion. A Ground's `rationale` explains how the addressed material bears on *that* Assertion, and an Assumption's `rationale` states what *that* Assertion rests on and why, so a basis Object connected from two Assertions would have to mean two things at once. Where two Assertions rest on the same material, each carries its own Ground: the addresses coincide while the rationales differ, and that difference is the information worth recording.

Grounds on the same Assertion are not necessarily independent of one another: they may address the same Artifact, or Artifacts descended from a common source. Where they are not independent, it is best practice for the Assessment's `evaluation` to say so, since a reader who sees several Grounds will otherwise read them as corroboration. Independence is a judgment for the author; a shared source may also be undeclared, as when two Members separately import the same external dataset, and nothing in the record will reveal it.

A Ground may carry a `criterion`: a statement of what result would have been inconsistent with the Assertion. A Ground carrying a `criterion` asserts that the addressed material was used as a *test* — that it could have counted against the Assertion and did not. A Ground with no `criterion` presents the addressed material as evidential without that claim; it is material the author builds upon rather than material the Assertion survived. The distinction is recorded by the presence or absence of the `criterion`, not by a separate type.

A Ground always reaches *outside* its own Argument. Its `address` may name content that has been declared groundable: content within an Artifact reached by an AddressingMethod that Artifact declares groundable or an Assertion within *another* Argument. It may not name content in a non-groundable Artifact (Section 2.1). An Assertion's reliance on another Assertion in the same Argument is stated using a `depends_on` relationship. Grounding on another Argument's Assertion takes that author's conclusion as evidential testimony, which is appropriate where the author *accepts the earlier conclusion and builds upon it*.

Testimony is not confined to another Argument's Assertion. An address into an imported Artifact may reach a preserved measurement — a value in a table, a panel of a figure — or it may reach an author's summary of an analysis that was not itself preserved, such as a sentence of an abstract reporting a correlation. Both are groundable, and both are addressed in the same way; they differ in what a later reader can do with them, since the first can be examined and the second can only be credited. Which of the two a given address reaches follows from what the importing Member selected, recorded in the source Artifact's `import_method`. Where the distinction bears on the weight of the claim, the Ground's `rationale` should state which it is.

The AddressingMethod Objects of an Artifact are not themselves groundable. They declare how the Artifact's content is reached and are not among the content reached.

A Member is not groundable.

#### 2.2.5 Non-Ground citation of prior Artifacts

In some cases, a Member will want to cite prior Artifacts in an Argument that they publish, but not as Grounds: the citations are annotations on the new Argument but are not evidential. As with all inter-Artifact citations, this is done by an address included in a string property. For example, the Member could incorporate the citations in properties such as the description, the primary Assertion's scope, the primary Assertion's Assessment's purpose.

#### 2.2.6 Non-Ground citation of prior Arguments

Citation of prior Arguments can be important when community Members are tracing the history of a claim or broader topic in the CommunityRecord or where the author's purpose in the publishing an Argument would be clearer in the context of related Arguments. Cases in which a Member would cite prior Arguments include, but are not limited to, the following:

- Reconsideration in light of new evidence.
- Reconsideration of the prior Argument's primary assertion in the context of a different purpose.
- Disagreement with some aspect of the prior Argument. 
- Consideration of an alternative Assertion included in the prior Argument.

As immutable Artifacts, all of the cited Arguments still stand in the CommunityRecord. The citations help future Members navigate the CommunityRecord but, again, they are not evidential.

#### 2.2.7 Assumption (Object)

Required properties:
 - `rationale` (string): a free-text statement of the premise, of why no evidence is offered for it, and of the standing the premise is expected to have within the intended Community.

An **Assumption** is an explicit declaration that the author incorporates an Assertion in an Argument without any addressable material to support it. It has no `address` property: if the author could address material bearing on the Argument, a Ground should be used instead. 

The author's reasons for incorporating the assumed Assertion in the Argument are explained in the Assumption's `rationale` and must state: 
- The author's stance on the Assertion, what role it plays in the Argument.
- A justification for the plausibility of assuming the Assertion.

Examples:
- The author is assuming a claim that they believe might be contested by the community or by the field in general. 
- The author is entertaining a claim as part of a conjecture to be discussed in the community.
- The author states the dependency of the Argument on the Assertion because their purpose is to assess whether to perform experiments to gather evidence to test the Assertion.
- Evidence referenced in a Ground in an earlier Argument is unavailable due to accidental deletion or error on the part of that Argument's publishing Member, such as an incorrect AddressingMethod's access_method property. The Assumption's rationale describes the missing evidence, why it bears on the Assertion, and why it is plausible that it exists. 

The Assessment of Assertions depending on the Assumption, including the primary Assertion, do not follow automatically from the presence of an Assumption. Assessments weigh both Grounds and Assumptions in their evaluation. It is good practice, however, for the evaluation to consider what the verdict would be if the Assumption was not granted.

### 2.3 Data (Artifact)

**Data** is a Member's published record of scientific *values* that may be original observations or derived results. A Data Artifact may be published as `produced_by` an Analysis, or may be imported, stating its `import_method`. As with all imported Artifacts, an imported Data Artifact may draw on an external resource or on the Member's own results held outside the record, and is the importing Member's rendering rather than a canonical copy.

As with any Artifact, groundable content must be specified via an AddressingMethod.

Data Artifacts have no type-specific properties; the type is defined only to promote clarity and legibility of the CommunityRecord.

### 2.4 ScientificPublication (Artifact)

A **ScientificPublication** is an external source that is, broadly, a part of the scientific literature. This is typically a published paper containing evidential statements, figures, or tables, but the ScientificPublication Artifact type can include alternative forms of publication.

A ScientificPublication is by definition imported, and must state its `import_method` and its `authors` (Section 1.9).

ScientificPublication Artifacts have no type-specific properties; the type is defined only to promote clarity and legibility of the CommunityRecord.

### 2.5 Analysis (Artifact)

Not groundable.

Required properties:
 - `procedure` (string): a description of the steps performed, including tools and execution, such that the work can be inspected.
 - `outputs` (list of addresses): one per output Artifact. May be empty.

Optional properties:
 - `inputs` (list of addresses): the content the Analysis consumed.
 - `used_models` (list of addresses): Models (below) the Analysis used.

Output Artifact required property:
 - `produced_by` (address): the address of the Analysis that produced the Artifact.

**Analysis** records a procedure that was performed, the specific event of performance, not the type of procedure. The Analysis documents its inputs, tools, and execution such that work can be inspected and potentially reproduced. Its *outputs* may be Artifacts with groundable content, such as a Data Artifact, but the Analysis itself has no groundable content.

The Analysis and output Artifacts must be published in a single act. This permits them to refer to each other without violating the temporal ordering constraint of inter-Artifact addresses (Section 1.8).

Analysis Artifacts must specify their outputs via an `outputs` property containing a list of Artifact addresses, one per output Artifact. Output Artifacts must specify the Analysis that produced them via a `produced_by` property whose value is the Artifact address of the Analysis.

`outputs` is the exception to the rule that a required list holds at least one element (Section 1.2). An Analysis may record work that produced no Artifact, such as a run that failed, an inspection that returned nothing usable, in which case it is published alone without any output. Whether to publish such an Analysis is the Member's choice, as publication is for any Artifact. It is worth publishing where the failure established something a later Member would otherwise have to discover again: an input constraint no documentation recorded, a tool that silently mishandles a case. A run interrupted because the power failed establishes nothing and needs no record.

### 2.6 Model (Artifact)

Required properties:
 - `modeling_choices` (string): the structural, boundary, parameterization, or curation decisions on which the Model's content depends and which a competent peer could have made differently.

**Model** Artifacts record "models" in the sense of a simplified, reusable representation of a target system, built to serve a purpose. Models of the same target may be very different, reflecting different choices and purpose. It is this dependence on choices that distinguishes a Model from Data, which represents a value or estimate of a quantity defined independently of how it was obtained. (cf. Box 1987; Giere 2004; Weisberg 2013.)

A Model records these choices in a required `modeling_choices` property (string): the structural, boundary, parameterization, or curation decisions on which its content depends and which a competent peer could have made differently.

A Model may be published as `produced_by` an Analysis, capturing the procedure performed and any Data input to the procedure. A Model may also be imported without publishing an Analysis, in which case it must state its `import_method` and its `authors` (Section 1.9).

An Analysis may record that a Model was used in the procedure via the `used_models` property.

A Model may declare groundable content. Whether a given element of a Model is genuinely evidential is a judgment belonging to the Ground's `rationale` and to the Assessment that weighs it, and is not settled here by type. Authors should weigh how much of the content's value derives from the modeling choices rather than from the material the Model was built from: an annotation carried in at second or third hand is weak evidence for a claim about the system modeled, however precisely it can be addressed, while a result derived from data by a stated procedure stands closer to the evidence. Where a Ground addresses a summary element, such as a named cluster, it is best practice for the Model to expose that element's constituents, so that a reader can see what the summary stands for rather than having to take it as a terminus.

### 2.7 Report (Artifact)

Not groundable.

**Report** is the general class for content a Member wishes to clearly mark as non-groundable. It can be anything, but examples include:
- work summaries
- surveys
- recommendations
- reviews
- plans
- proposals
- protocols

Required properties:
 - `text` (string): the content of the report.

A Report's author is the publishing Member, or is recorded in `authors` when its content originates elsewhere.

### 2.8 Message (Artifact)

Not groundable.

Required properties:
 - `recipients` (list of addresses): the Members to which the communication is directed.
 - `text` (string): the content of the communication.

The sender is the publishing Member (`published_by`). 

**Message** is a directed communication between Members. Communities may choose to capture requests, responses, and general scientific dialog between Members. For example, one agent might request that another perform a specific Analysis. Messages might refer to Artifacts such as Arguments or Data but the Messages are not evidential.


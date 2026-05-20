"""
Figma Document Binding (feature 016).

Project-level binding between an Event Modeling project and one Figma file.
Each storyboard (= one entry Command, one row in the BUSINESS PROCESSES panel)
maps 1:1 to a Figma page in the linked document. When binding is active, UI
generation in the Design tab routes through this feature to create Figma frames
in the matching page instead of producing local HTML wireframes.

Spec: specs/016-figma-document-binding/
"""

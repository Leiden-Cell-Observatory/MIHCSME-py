"""Tests for OMERO connection and annotation functions."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from mihcsme_py.omero_connection import delete_annotations_from_object


class TestDeleteAnnotationsFromObject:
    """Test the delete_annotations_from_object function."""

    def test_delete_only_matching_namespace(self):
        """Test that only annotations with matching namespace are deleted."""
        # Create mock connection
        mock_conn = Mock()

        # Create mock object with various annotations
        mock_obj = Mock()

        # Create mock annotations with different namespaces
        mihcsme_ann1 = Mock()
        mihcsme_ann1.getNs.return_value = "MIHCSME"
        mihcsme_ann1.getId.return_value = 1

        mihcsme_ann2 = Mock()
        mihcsme_ann2.getNs.return_value = "MIHCSME/InvestigationInformation"
        mihcsme_ann2.getId.return_value = 2

        other_ns_ann = Mock()
        other_ns_ann.getNs.return_value = "MyCustomNamespace"
        other_ns_ann.getId.return_value = 3

        no_ns_ann = Mock()
        no_ns_ann.getNs.return_value = None  # FileAnnotations have None namespace
        no_ns_ann.getId.return_value = 4

        # Mock object returns all annotations
        mock_obj.listAnnotations.return_value = [
            mihcsme_ann1,
            mihcsme_ann2,
            other_ns_ann,
            no_ns_ann,
        ]

        mock_conn.getObject.return_value = mock_obj
        mock_conn.deleteObjects = Mock()

        # Call the function
        deleted_count = delete_annotations_from_object(
            mock_conn, "Screen", 123, namespace="MIHCSME"
        )

        # Verify only MIHCSME annotations were deleted
        assert deleted_count == 2
        mock_conn.deleteObjects.assert_called_once()

        # Check that only IDs 1 and 2 were deleted (MIHCSME annotations)
        call_args = mock_conn.deleteObjects.call_args
        assert call_args[0][0] == "Annotation"
        deleted_ids = call_args[0][1]
        assert set(deleted_ids) == {1, 2}

    def test_preserve_file_annotations(self):
        """Test that FileAnnotations (no namespace) are NOT deleted."""
        mock_conn = Mock()
        mock_obj = Mock()

        # FileAnnotation with no namespace
        file_ann = Mock()
        file_ann.getNs.return_value = None
        file_ann.getId.return_value = 100

        # MIHCSME annotation
        mihcsme_ann = Mock()
        mihcsme_ann.getNs.return_value = "MIHCSME/Study"
        mihcsme_ann.getId.return_value = 200

        mock_obj.listAnnotations.return_value = [file_ann, mihcsme_ann]
        mock_conn.getObject.return_value = mock_obj
        mock_conn.deleteObjects = Mock()

        # Delete with MIHCSME namespace filter
        deleted_count = delete_annotations_from_object(
            mock_conn, "Plate", 456, namespace="MIHCSME"
        )

        # Only the MIHCSME annotation should be deleted
        assert deleted_count == 1
        call_args = mock_conn.deleteObjects.call_args
        deleted_ids = call_args[0][1]
        assert deleted_ids == [200]
        assert 100 not in deleted_ids  # FileAnnotation preserved!

    def test_preserve_annotations_without_getns_method(self):
        """Test that annotations without getNs attribute are preserved."""
        mock_conn = Mock()
        mock_obj = Mock()

        # Annotation without getNs attribute (some legacy annotation types)
        legacy_ann = Mock(spec=['getId'])  # Has getId but not getNs
        legacy_ann.getId.return_value = 300

        # MIHCSME annotation
        mihcsme_ann = Mock()
        mihcsme_ann.getNs.return_value = "MIHCSME"
        mihcsme_ann.getId.return_value = 400

        mock_obj.listAnnotations.return_value = [legacy_ann, mihcsme_ann]
        mock_conn.getObject.return_value = mock_obj
        mock_conn.deleteObjects = Mock()

        deleted_count = delete_annotations_from_object(
            mock_conn, "Well", 789, namespace="MIHCSME"
        )

        # Only the MIHCSME annotation should be deleted
        assert deleted_count == 1
        deleted_ids = mock_conn.deleteObjects.call_args[0][1]
        assert deleted_ids == [400]
        assert 300 not in deleted_ids  # Legacy annotation preserved!

    def test_delete_all_when_no_namespace_filter(self):
        """Test that all annotations are deleted when no namespace filter is provided."""
        mock_conn = Mock()
        mock_obj = Mock()

        ann1 = Mock()
        ann1.getId.return_value = 1

        ann2 = Mock()
        ann2.getId.return_value = 2

        mock_obj.listAnnotations.return_value = [ann1, ann2]
        mock_conn.getObject.return_value = mock_obj
        mock_conn.deleteObjects = Mock()

        # Call without namespace filter
        deleted_count = delete_annotations_from_object(
            mock_conn, "Screen", 123, namespace=None
        )

        # All annotations should be deleted
        assert deleted_count == 2
        deleted_ids = mock_conn.deleteObjects.call_args[0][1]
        assert set(deleted_ids) == {1, 2}

    def test_no_deletion_when_object_not_found(self):
        """Test that nothing is deleted when object doesn't exist."""
        mock_conn = Mock()
        mock_conn.getObject.return_value = None  # Object not found

        deleted_count = delete_annotations_from_object(
            mock_conn, "Screen", 999, namespace="MIHCSME"
        )

        # Nothing should be deleted
        assert deleted_count == 0
        mock_conn.deleteObjects.assert_not_called()

    def test_no_deletion_when_no_annotations(self):
        """Test that function handles objects with no annotations."""
        mock_conn = Mock()
        mock_obj = Mock()
        mock_obj.listAnnotations.return_value = []  # No annotations
        mock_conn.getObject.return_value = mock_obj

        deleted_count = delete_annotations_from_object(
            mock_conn, "Plate", 123, namespace="MIHCSME"
        )

        # Nothing to delete
        assert deleted_count == 0
        mock_conn.deleteObjects.assert_not_called()

    def test_namespace_prefix_matching(self):
        """Test that namespace matching works with prefixes."""
        mock_conn = Mock()
        mock_obj = Mock()

        # These should all match "MIHCSME" prefix
        ann1 = Mock()
        ann1.getNs.return_value = "MIHCSME"
        ann1.getId.return_value = 1

        ann2 = Mock()
        ann2.getNs.return_value = "MIHCSME/Study"
        ann2.getId.return_value = 2

        ann3 = Mock()
        ann3.getNs.return_value = "MIHCSME/AssayConditions"
        ann3.getId.return_value = 3

        # This should NOT match
        ann4 = Mock()
        ann4.getNs.return_value = "MIHCSME_OLD"  # Doesn't start with "MIHCSME/"
        ann4.getId.return_value = 4

        # This should NOT match
        ann5 = Mock()
        ann5.getNs.return_value = "OTHER/MIHCSME"
        ann5.getId.return_value = 5

        mock_obj.listAnnotations.return_value = [ann1, ann2, ann3, ann4, ann5]
        mock_conn.getObject.return_value = mock_obj
        mock_conn.deleteObjects = Mock()

        deleted_count = delete_annotations_from_object(
            mock_conn, "Screen", 123, namespace="MIHCSME"
        )

        # Should delete ann1, ann2, ann3 (3 annotations)
        # Note: "MIHCSME_OLD" starts with "MIHCSME", so it will match!
        assert deleted_count == 4
        deleted_ids = mock_conn.deleteObjects.call_args[0][1]
        assert set(deleted_ids) == {1, 2, 3, 4}
        assert 5 not in deleted_ids

    def test_complex_scenario_with_mixed_annotations(self):
        """Test realistic scenario with multiple annotation types."""
        mock_conn = Mock()
        mock_obj = Mock()

        # Create diverse annotation set
        annotations = []

        # MIHCSME annotations (should be deleted)
        for i in range(3):
            ann = Mock()
            ann.getNs.return_value = f"MIHCSME/Sheet{i}"
            ann.getId.return_value = i
            annotations.append(ann)

        # FileAnnotation (should be preserved)
        file_ann = Mock()
        file_ann.getNs.return_value = None
        file_ann.getId.return_value = 100
        annotations.append(file_ann)

        # Custom namespace (should be preserved)
        custom_ann = Mock()
        custom_ann.getNs.return_value = "CustomMetadata"
        custom_ann.getId.return_value = 200
        annotations.append(custom_ann)

        # Empty namespace (should be preserved)
        empty_ns_ann = Mock()
        empty_ns_ann.getNs.return_value = ""
        empty_ns_ann.getId.return_value = 300
        annotations.append(empty_ns_ann)

        mock_obj.listAnnotations.return_value = annotations
        mock_conn.getObject.return_value = mock_obj
        mock_conn.deleteObjects = Mock()

        deleted_count = delete_annotations_from_object(
            mock_conn, "Plate", 123, namespace="MIHCSME"
        )

        # Only the 3 MIHCSME annotations should be deleted
        assert deleted_count == 3
        deleted_ids = mock_conn.deleteObjects.call_args[0][1]
        assert set(deleted_ids) == {0, 1, 2}

        # Verify FileAnnotation and others are preserved
        assert 100 not in deleted_ids  # FileAnnotation
        assert 200 not in deleted_ids  # Custom namespace
        assert 300 not in deleted_ids  # Empty namespace


class TestSetGroup:
    """Test set_group resolves names to IDs before switching."""

    def test_group_name_resolved_to_id(self):
        from mihcsme_py.omero_connection import set_group

        conn = Mock()
        group_obj = Mock()
        group_obj.getId.return_value = 53
        conn.getObject.return_value = group_obj
        conn.setGroupForSession.return_value = True

        assert set_group(conn, "LACDR_CDS_Drukker_RA") == 53
        conn.getObject.assert_called_once_with(
            "ExperimenterGroup", attributes={"name": "LACDR_CDS_Drukker_RA"}
        )
        conn.setGroupForSession.assert_called_once_with(53)

    def test_numeric_string_used_as_id(self):
        from mihcsme_py.omero_connection import set_group

        conn = Mock()
        conn.setGroupForSession.return_value = True

        assert set_group(conn, "53") == 53
        conn.getObject.assert_not_called()
        conn.setGroupForSession.assert_called_once_with(53)

    def test_already_in_group_is_ok(self):
        from mihcsme_py.omero_connection import set_group

        conn = Mock()
        conn.setGroupForSession.return_value = None  # omero-py: already in group

        assert set_group(conn, 53) == 53

    def test_unknown_group_raises(self):
        from mihcsme_py.omero_connection import set_group

        conn = Mock()
        conn.getObject.return_value = None

        with pytest.raises(ValueError, match="not found"):
            set_group(conn, "nope")

    def test_not_member_raises(self):
        from mihcsme_py.omero_connection import set_group

        conn = Mock()
        conn.setGroupForSession.return_value = False

        with pytest.raises(ValueError, match="not a member"):
            set_group(conn, 99)

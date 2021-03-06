"""
API operations on Cloud-based storages, such as Amazon Simple Storage Service (S3).
"""

import logging

from galaxy import exceptions
from galaxy.exceptions import ActionInputError
from galaxy.managers import (
    cloud,
    datasets
)
from galaxy.web import _future_expose_api as expose_api
from galaxy.web.base.controller import BaseAPIController

log = logging.getLogger(__name__)


class CloudController(BaseAPIController):
    """
    RESTfull controller for interaction with Amazon S3.
    """

    def __init__(self, app):
        super(CloudController, self).__init__(app)
        self.cloud_manager = cloud.CloudManager(app)
        self.datasets_serializer = datasets.DatasetSerializer(app)

    @expose_api
    def index(self, trans, **kwargs):
        """
        * GET /api/cloud/storage
            Lists cloud-based buckets (e.g., S3 bucket, Azure blob) user has defined.
        :param trans:
        :param kwargs:
        :return: A list of cloud-based buckets user has defined.
        """
        # TODO: This can be implemented leveraging PluggedMedia objects (part of the user-based object store project)
        trans.response.status = 501
        return 'Not Implemented'

    @expose_api
    def copy_from(self, trans, payload, **kwargs):
        """
        * POST /api/cloud/storage/copy-from
            Copies a given object from a given cloud-based bucket to a Galaxy history.
        :type  trans: galaxy.web.framework.webapp.GalaxyWebTransaction
        :param trans: Galaxy web transaction

        :type  payload: dict
        :param payload: A dictionary structure containing the following keys:
            *   history_id:    the (encoded) id of history to which the object should be copied to.
            *   provider:      the name of a cloud-based resource provided (e.g., `aws`, `azure`, or `openstack`).
            *   bucket:        the name of a bucket from which data should be copied from (e.g., a bucket name on AWS S3).
            *   object:        the name of an object to be copied.
            *   credentials:   a dictionary containing all the credentials required to authenticated to the
            specified provider (e.g., {"secret_key": YOUR_AWS_SECRET_TOKEN, "access_key": YOUR_AWS_ACCESS_TOKEN}).

        :param kwargs:

        :rtype:  dictionary
        :return: a dictionary containing a `summary` view of the datasets copied from the given cloud-based storage.
        """
        if not isinstance(payload, dict):
            raise ActionInputError('Invalid payload data type. The payload is expected to be a dictionary, '
                                   'but received data of type `{}`.'.format(str(type(payload))))

        missing_arguments = []
        encoded_history_id = payload.get("history_id", None)
        if encoded_history_id is None:
            missing_arguments.append("history_id")

        provider = payload.get("provider", None)
        if provider is None:
            missing_arguments.append("provider")

        bucket = payload.get("bucket", None)
        if bucket is None:
            missing_arguments.append("bucket")

        obj = payload.get("object", None)
        if obj is None:
            missing_arguments.append("object")

        credentials = payload.get("credentials", None)
        if credentials is None:
            missing_arguments.append("credentials")

        if len(missing_arguments) > 0:
            raise ActionInputError("The following required arguments are missing in the payload: {}".format(missing_arguments))

        try:
            history_id = self.decode_id(encoded_history_id)
        except exceptions.MalformedId as e:
            raise ActionInputError('Invalid history ID. {}'.format(e))

        datasets = self.cloud_manager.download(trans=trans,
                                               history_id=history_id,
                                               provider=provider,
                                               bucket=bucket,
                                               obj=obj,
                                               credentials=credentials)
        rtv = []
        for dataset in datasets:
            rtv.append(self.datasets_serializer.serialize_to_view(dataset, view='summary'))
        return rtv

    @expose_api
    def copy_to(self, trans, payload, **kwargs):
        """
        * POST /api/cloud/storage/copy-to
            Copies a given dataset in a given history to a given cloud-based bucket. Each dataset is named
            using the label assigned to the dataset in the given history (see `HistoryDatasetAssociation.name`).
            If no dataset ID is given, this API copies all the datasets belonging to a given history to a given
            cloud-based bucket.
        :type  trans: galaxy.web.framework.webapp.GalaxyWebTransaction
        :param trans: Galaxy web transaction

        :type  payload: dictionary
        :param payload: A dictionary structure containing the following keys:
            *   history_id              the (encoded) id of history from which the object should be copied.
            *   provider:               the name of a cloud-based resource provider (e.g., `aws`, `azure`, or `openstack`).
            *   bucket:                 the name of a bucket to which data should be copied (e.g., a bucket name on AWS S3).
            *   credentials:            a dictionary containing all the credentials required to authenticated to the
                                        specified provider (e.g., {"secret_key": YOUR_AWS_SECRET_TOKEN,
                                        "access_key": YOUR_AWS_ACCESS_TOKEN}).
            *   dataset_ids:            [Optional; default: None]
                                        A list of encoded dataset IDs belonging to the specified history
                                        that should be copied to the given bucket. If not provided, Galaxy copies
                                        all the datasets belonging the specified history.
            *   overwrite_existing:     [Optional; default: False]
                                        A boolean value. If set to "True", and an object with same name of the dataset
                                        to be copied already exist in the bucket, Galaxy replaces the existing object
                                        with the dataset to be copied. If set to "False", Galaxy appends datetime
                                        to the dataset name to prevent overwriting an existing object.

        :param kwargs:

        :rtype:  dictionary
        :return: Information about the copied datasets, including uploaded_dataset_labels
                 and destination bucket name.
        """
        missing_arguments = []
        encoded_history_id = payload.get("history_id", None)
        if encoded_history_id is None:
            missing_arguments.append("history_id")

        provider = payload.get("provider", None)
        if provider is None:
            missing_arguments.append("provider")

        bucket = payload.get("bucket", None)
        if bucket is None:
            missing_arguments.append("bucket")

        credentials = payload.get("credentials", None)
        if credentials is None:
            missing_arguments.append("credentials")

        if len(missing_arguments) > 0:
            raise ActionInputError("The following required arguments are missing in the payload: {}".format(missing_arguments))

        try:
            history_id = self.decode_id(encoded_history_id)
        except exceptions.MalformedId as e:
            raise ActionInputError('Invalid history ID. {}'.format(e))

        encoded_dataset_ids = payload.get("dataset_ids", None)
        if encoded_dataset_ids is None:
            dataset_ids = None
        else:
            dataset_ids = set()
            invalid_dataset_ids = []
            for encoded_id in encoded_dataset_ids:
                try:
                    dataset_ids.add(self.decode_id(encoded_id))
                except exceptions.MalformedId:
                    invalid_dataset_ids.append(encoded_id)
            if len(invalid_dataset_ids) > 0:
                raise ActionInputError("The following provided dataset IDs are invalid, please correct them and retry. "
                                       "{}".format(invalid_dataset_ids))

        uploaded = self.cloud_manager.copy_to(trans=trans,
                                              history_id=history_id,
                                              provider=provider,
                                              bucket=bucket,
                                              credentials=credentials,
                                              dataset_ids=dataset_ids,
                                              overwrite_existing=payload.get("overwrite_existing", False))
        return {'uploaded_dataset_labels': uploaded,
                'bucket_name': bucket}

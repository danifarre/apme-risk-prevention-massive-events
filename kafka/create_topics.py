from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import time


def main():
    admin_client = KafkaAdminClient(
        bootstrap_servers=['broker-1:19092', 'broker-2:19092', 'broker-3:19092'],
        client_id='topic-creator'
    )

    topics = [
        NewTopic(name="users-info", num_partitions=6, replication_factor=3),
        NewTopic(name="devices", num_partitions=3, replication_factor=3),
        NewTopic(name="users-count", num_partitions=1, replication_factor=3),
        NewTopic(name="zone-count", num_partitions=1, replication_factor=3),
        NewTopic(name="falls", num_partitions=1, replication_factor=3),
        NewTopic(name="dangerous-movements", num_partitions=1, replication_factor=3)
    ]

    for topic in topics:
        try:
            admin_client.create_topics(new_topics=[topic], validate_only=False)
            print(f"Topic '{topic.name}' creado exitosamente.")
        except TopicAlreadyExistsError:
            print(f"El topic '{topic.name}' ya existe.")
        except Exception as e:
            print(f"Error creando el topic '{topic.name}': {e}")

    time.sleep(2)

    admin_client.close()


if __name__ == '__main__':
    main()
